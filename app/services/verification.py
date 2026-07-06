from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone

from app.core.database import get_db
from app.core.security import create_verification_token, verify_merchant_auth
from app.models.verification import VerificationSession, SessionStatus
from app.models.audit import AuditLog


router = APIRouter(prefix="/sessions", tags=["Verification Sessions"])

class CreateSessionRequest(BaseModel):
    expected_amount: float
    expiration_minutes: int = 15

class SessionResponse(BaseModel):
    session_id: int
    token: str
    expires_at: datetime
    status: str

@router.post("/create", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest,
    db: AsyncSession = Depends(get_db),
    merchant: dict = Depends(verify_merchant_auth)):
    """
    Step 1 of Production Flow: Backend creates a signed verification token 
    and registers a pending verification session.
    """
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=request.expiration_minutes)
    
    # Pre-save session to acquire a unique database ID
    new_session = VerificationSession(
        expected_amount=request.expected_amount,
        status=SessionStatus.PENDING,
        expires_at=expires_at,
        token="PENDING_GENERATION" # Placeholder
    )
    db.add(new_session)
    await db.flush() # Flushes to database to populate new_session.id
    
    # Generate the signed JWT incorporating the persistent session details
    generated_token = create_verification_token(
        session_id=str(new_session.id), 
        expected_amount=request.expected_amount
    )
    new_session.token = generated_token
    
    # Create the immutable audit trail
    audit = AuditLog(
        action="SESSION_CREATED",
        entity_name="VerificationSession",
        entity_id=str(new_session.id),
        payload={"expected_amount": request.expected_amount, "expires_at": expires_at.isoformat()}
    )
    db.add(audit)
    
    await db.commit()
    await db.refresh(new_session)
    
    return {
        "session_id": new_session.id,
        "token": new_session.token,
        "expires_at": new_session.expires_at,
        "status": new_session.status
    }