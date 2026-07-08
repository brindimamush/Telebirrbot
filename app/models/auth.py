# app/models/auth.py
from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, DateTime, Enum
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base

class AdminRole(str, enum.Enum):
    SUPERADMIN = "superadmin"
    SUPPORT = "support"
    FINANCE = "finance"

class AdminUser(Base):
    __tablename__ = "admin_users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(AdminRole), default=AdminRole.SUPPORT, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class MerchantAPIKey(Base):
    """Supports multiple keys per merchant, rotation, and IP whitelisting."""
    __tablename__ = "merchant_api_keys"
    id = Column(Integer, primary_key=True, index=True)
    merchant_id = Column(Integer, ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False) # e.g., "Production Key", "Test Key"
    prefix = Column(String, nullable=False) # First 8 chars for UI identification
    key_hash = Column(String, unique=True, index=True, nullable=False)
    ip_whitelist = Column(ARRAY(INET), nullable=True) # Allowed IPs
    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)

class LoginHistory(Base):
    """Audit trail for dashboard access."""
    __tablename__ = "login_history"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False) # Can be AdminUser.id or Merchant.id
    user_type = Column(String, nullable=False) # "ADMIN" or "MERCHANT"
    ip_address = Column(INET, nullable=True)
    user_agent = Column(String, nullable=True)
    status = Column(String, nullable=False) # "SUCCESS", "FAILED"
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

class DeviceRegistration(Base):
    """PlayIntegrity and SSL Pinning verified devices from the Flutter App."""
    __tablename__ = "device_registrations"
    id = Column(Integer, primary_key=True, index=True)
    merchant_id = Column(Integer, ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False)
    device_fingerprint = Column(String, unique=True, index=True, nullable=False)
    hardware_id = Column(String, nullable=False)
    is_trusted = Column(Boolean, default=True, nullable=False)
    registered_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())