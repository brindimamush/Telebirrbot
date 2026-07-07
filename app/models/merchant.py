from sqlalchemy import Column, String, Integer, Boolean, DateTime, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class Merchant(Base):
    """Represents a business entity authorized to manage verification sessions."""
    __tablename__ = "merchants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    #fields for automated Telegram onboarding
    telegram_user_id = Column(BigInteger, unique=True, index=True, nullable=False)
    payment_phone = Column(String, nullable=False)
    subscription_expires_at = Column(DateTime(timezone=True), nullable=True)
    # Store hashes of API keys in the database, never the raw values
    api_key_hash = Column(String, unique=True, index=True, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship linking back to sessions owned by this merchant
    sessions = relationship("VerificationSession", back_populates="merchant", cascade="all, delete-orphan")