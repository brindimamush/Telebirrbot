from sqlalchemy import Column, String, Float, DateTime, Enum, Integer
from sqlalchemy.sql import func
import enum
from app.core.database import Base

class SessionStatus(str, enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"
    EXPIRED = "expired"

class VerificationSession(Base):
    __tablename__ = "verification_sessions"

    id = Column(Integer, primary_key=True, index=True)
    # The signed verification token, indexed for fast lookup from Flutter
    token = Column(String, unique=True, index=True, nullable=False)
    expected_amount = Column(Float, nullable=False)
    status = Column(Enum(SessionStatus), default=SessionStatus.PENDING)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)