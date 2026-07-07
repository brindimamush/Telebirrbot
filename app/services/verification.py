from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from pydantic import BaseModel, Field
from datetime import datetime, timedelta, timezone

from app.core.database import get_db
from app.core.security import create_verification_token, verify_merchant_api_key
from app.models.verification import VerificationSession, SessionStatus
from app.models.audit import AuditLog
from app.models.merchant import Merchant


router = APIRouter(prefix="/sessions", tags=["Verification Sessions"])

class CreateSessionRequest(BaseModel):
    expected_amount: float = Field(..., gt=0.0, description="The precise amount to pass verification.")
    expiration_minutes: int = Field(default=15, ge=5, le=1440)

class SessionResponse(BaseModel):
    session_id: int
    merchant_id: int
    token: str
    expires_at: datetime
    status: SessionStatus
    expected_amount: float

    class Config:
        from_attributes = True

class SessionPaginatedHistory(BaseModel):
    total_records: int
    page: int
    limit: int
    data: list[SessionResponse]

# --- API Routes ---

@router.post("/create", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    request: CreateSessionRequest,
    db: AsyncSession = Depends(get_db),
    merchant: Merchant = Depends(verify_merchant_api_key)
):
    """Creates a cryptographic verification context owned implicitly by the calling merchant."""
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=request.expiration_minutes)
    
    new_session = VerificationSession(
        merchant_id=merchant.id,
        expected_amount=request.expected_amount,
        status=SessionStatus.PENDING,
        expires_at=expires_at,
        token="PENDING_GENERATION"
    )
    db.add(new_session)
    await db.flush()
    
    generated_token = create_verification_token(
        session_id=str(new_session.id), 
        expected_amount=request.expected_amount
    )
    new_session.token = generated_token
    
    audit = AuditLog(
        action="SESSION_CREATED",
        entity_name="VerificationSession",
        entity_id=str(new_session.id),
        payload={
            "merchant_id": merchant.id,
            "expected_amount": request.expected_amount, 
            "expires_at": expires_at.isoformat()
        }
    )
    db.add(audit)
    await db.commit()
    await db.refresh(new_session)
    return new_session


@router.get("/lookup/{session_id}", response_model=SessionResponse)
async def lookup_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    merchant: Merchant = Depends(verify_merchant_api_key)
):
    """Retrieves context for a single verification session while asserting strict merchant ownership."""
    result = await db.execute(
        select(VerificationSession).where(
            VerificationSession.id == session_id,
            VerificationSession.merchant_id == merchant.id
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verification session records not found.")
    return session


@router.post("/cancel/{session_id}", response_model=SessionResponse)
async def cancel_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    merchant: Merchant = Depends(verify_merchant_api_key)
):
    """Terminates a pending verification session manually, neutralizing downstream link validations."""
    result = await db.execute(
        select(VerificationSession).where(
            VerificationSession.id == session_id,
            VerificationSession.merchant_id == merchant.id
        )
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verification session context missing.")
    if session.status != SessionStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Only PENDING sessions can be cancelled. Current status is: {session.status}"
        )
        
    session.status = SessionStatus.CANCELLED
    
    audit = AuditLog(
        action="SESSION_CANCELLED",
        entity_name="VerificationSession",
        entity_id=str(session.id),
        payload={"merchant_id": merchant.id, "cancelled_at": datetime.now(timezone.utc).isoformat()}
    )
    db.add(audit)
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/history", response_model=SessionPaginatedHistory)
async def get_session_history(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    status_filter: SessionStatus = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
    merchant: Merchant = Depends(verify_merchant_api_key)
):
    """Returns a cursor-paginated, filterable historical record list of sessions owned by the merchant."""
    offset = (page - 1) * limit
    
    # Assemble structured conditional statements dynamically
    base_stmt = select(VerificationSession).where(VerificationSession.merchant_id == merchant.id)
    if status_filter:
        base_stmt = base_stmt.where(VerificationSession.status == status_filter)
        
    # Query exact total matching count 
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total_count_res = await db.execute(count_stmt)
    total_records = total_count_res.scalar_one()
    
    # Query data payload slice sorted chronologically
    data_stmt = base_stmt.order_by(VerificationSession.created_at.desc()).offset(offset).limit(limit)
    data_res = await db.execute(data_stmt)
    sessions = data_res.scalars().all()
    
    return {
        "total_records": total_records,
        "page": page,
        "limit": limit,
        "data": sessions
    }