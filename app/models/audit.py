from sqlalchemy import Column, String, DateTime, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.core.database import Base

class AuditLog(Base):
    """Immutable audit logs for all system actions."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String, index=True, nullable=False)  # e.g., "SESSION_CREATED", "RECEIPT_VERIFIED"
    entity_name = Column(String, nullable=False)         # e.g., "TransactionReceipt"
    entity_id = Column(String, nullable=False)
    payload = Column(JSONB, nullable=False)              # Stores the exact state/data 
    created_at = Column(DateTime(timezone=True), server_default=func.now())