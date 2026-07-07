from sqlalchemy import Column, String, Float, DateTime, Integer
from sqlalchemy.sql import func
from app.core.database import Base

class PlatformSettings(Base):
    """Dynamic configuration for platform monetization."""
    __tablename__ = "platform_settings"

    id = Column(Integer, primary_key=True, index=True)
    monthly_fee = Column(Float, nullable=False, default=150.00)
    receiver_phone = Column(String, nullable=False)
    receiver_name = Column(String, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())