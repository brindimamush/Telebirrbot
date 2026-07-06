from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/validation", tags=["Validation"])

class ExtractedReceiptPayload(BaseModel):
    token: str  # The signed verification token
    txn_id: str
    payer_name: str
    credited_party_name: str
    credited_party_account: str
    settled_amount: float
    transaction_status: str

@router.post("/verify-receipt")
async def validate_receipt_submission(payload: ExtractedReceiptPayload):
    """
    Step 6 of production flow: Client sends extracted fields.
    Backend checks them against expected session variables.
    """
    # 1. TODO: Validate the JWT token signature and expiration
    # 2. TODO: Cross-verify payload.settled_amount == token.amt
    # 3. TODO: Check if txn_id has already been used (Idempotency check)
    
    if payload.transaction_status.lower() != "successful":
        raise HTTPException(status_code=400, detail="Transaction status is not marked as successful.")
        
    # 4. Trigger background tasks (Notification, Subscription, Audit) in later phases
    return {"status": "verified", "message": "Payment validated successfully."}