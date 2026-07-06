import jwt
from fastapi import APIRouter, HTTPException, Depends,status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from pydantic import BaseModel, field_validator

from app.core.config import settings
from app.core.database import get_db
from app.models.verification import VerificationSession, SessionStatus
from app.models.transaction import TransactionReceipt
from app.models.audit import AuditLog

router = APIRouter(prefix="/validation", tags=["Validation Engine"])

class ReceiptSubmission(BaseModel):
    token: str
    txn_id: str
    payer_name: str
    credited_party_name: str
    credited_party_account: str
    settled_amount: float
    transaction_status: str

    @field_validator("txn_id")
    @classmethod
    def clean_transaction_id(cls, v: str) -> str:
        """Sanitizes transaction IDs matching your existing strip pattern."""
        if not v or not "".join(v.split()):
            raise ValueError("Invalid Transaction ID structure.")
        return "".join(v.split()).upper()

@router.post("/verify-receipt")
async def verify_receipt(payload: ReceiptSubmission, db: AsyncSession = Depends(get_db)):
    """
    Step 6 of Production Flow: Validates extracted data against cryptographic session claims.
    Enforces transaction idempotency across the platform.
    """
    # 1. Decode and verify the cryptographic integrity of the incoming token
    try:
        decoded_token = jwt.decode(payload.token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        session_id = int(decoded_token.get("sub"))
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or tampered verification token.")

    # 2. Check strict transaction idempotency (Has this Telebirr TXNID been used before?)
    existing_txn = await db.execute(select(TransactionReceipt).where(TransactionReceipt.txn_id == payload.txn_id))
    if existing_txn.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This Transaction ID has already been verified.")

    # 3. Retrieve the localized verification session and check its validity state
    session_query = await db.execute(select(VerificationSession).where(VerificationSession.id == session_id))
    session: VerificationSession = session_query.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verification session context missing.")
    if session.status != SessionStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Session cannot be verified. Current status: {session.status}")
    if session.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        session.status = SessionStatus.EXPIRED
        await db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification session has expired.")

    # 4. Cross-verify parsed values against actual financial contract terms
    if abs(payload.settled_amount - session.expected_amount) > 0.01:
        session.status = SessionStatus.FAILED
        await db.commit()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Paid amount does not match expected session amount.")
        
    if payload.transaction_status.upper() != "SUCCESSFUL":
        session.status = SessionStatus.FAILED
        await db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Receipt status indicates an incomplete transaction.")

    # 5. Success State: Commit the transaction receipt to the log and close out the session
    session.status = SessionStatus.VERIFIED
    
    receipt = TransactionReceipt(
        txn_id=payload.txn_id,
        session_id=session.id,
        payer_name=payload.payer_name,
        credited_party_account=payload.credited_party_account,
        settled_amount=payload.settled_amount,
        transaction_status=payload.transaction_status
    )
    db.add(receipt)
    await db.flush() # Acquire receipt ID
    
    # 6. Build the immutable audit payload
    audit = AuditLog(
        action="RECEIPT_VERIFIED",
        entity_name="TransactionReceipt",
        entity_id=str(receipt.id),
        payload={
            "txn_id": payload.txn_id,
            "session_id": session.id,
            "settled_amount": payload.settled_amount
        }
    )
    db.add(audit)
    await db.commit()

    # 7. Return success context to Flutter client
    return {
        "status": "success",
        "message": f"Transaction {payload.txn_id} verified successfully.",
        "session_status": session.status
    }