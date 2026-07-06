from sqlalchemy import Column, String, Float, DateTime, Integer, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base

class TransactionReceipt(Base):
    __tablename__ = "transaction_receipts"

    id = Column(Integer, primary_key=True, index=True)
    # Unique index enforces idempotency - a transaction ID can only be verified once
    txn_id = Column(String, unique=True, index=True, nullable=False)
    session_id = Column(Integer, ForeignKey("verification_sessions.id"), nullable=False)
    
    payer_name = Column(String, nullable=True)
    credited_party_account = Column(String, nullable=True)
    settled_amount = Column(Float, nullable=False)
    transaction_status = Column(String, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())