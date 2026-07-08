# app/models/admin_extensions.py
from sqlalchemy import Column, String, Boolean, Float, DateTime, Integer, ForeignKey, JSON
from sqlalchemy.sql import func
from app.core.database import Base

class FeatureFlag(Base):
    """Dynamic configuration switches for rolling deployment toggles."""
    __tablename__ = "feature_flags"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True, nullable=False)
    description = Column(String, nullable=True)
    is_enabled = Column(Boolean, default=False, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DynamicParserRule(Base):
    """Database-backed routing rules matching parsing instructions for providers like Telebirr."""
    __tablename__ = "dynamic_parser_rules"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String, unique=True, index=True, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    target_url_template = Column(String, nullable=False)
    selectors = Column(JSON, nullable=False) # Stores selector paths cleanly
    is_active = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class FraudRecord(Base):
    """Tracks systemic high-risk transactional verification anomalies."""
    __tablename__ = "fraud_queue"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("verification_sessions.id", ondelete="SET NULL"), nullable=True)
    txn_id = Column(String, index=True, nullable=True)
    risk_score = Column(Float, nullable=False) # Scale 0.0 - 1.0
    flag_reason = Column(String, nullable=False) # e.g., "Mismatched Amount", "Velocity Trigger"
    is_resolved = Column(Boolean, default=False, nullable=False)
    resolution_notes = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())