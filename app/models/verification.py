from sqlalchemy import Column, String, Float, DateTime, Enum, Integer, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
import enum
from app.core.database import Base

class SessionStatus(str, enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"

class VerificationSession(Base):
    __tablename__ = "verification_sessions"

    id = Column(Integer, primary_key=True, index=True)
    merchant_id = Column(Integer, ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False)
    # The signed verification token, indexed for fast lookup from Flutter
    token = Column(String, unique=True, index=True, nullable=False)
    expected_amount = Column(Float, nullable=False)
    status = Column(Enum(SessionStatus), default=SessionStatus.PENDING)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Relationships
    merchant = relationship("Merchant", back_populates="sessions")
    # Stores context, e.g., {"action": "platform_subscription", "target_merchant_id": 123}
    metadata_payload = Column(JSONB, nullable=True)