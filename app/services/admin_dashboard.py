# app/services/admin_dashboard.py
import jwt
from typing import Optional, Any
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, update, delete, and_, or_
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.database import get_db
from app.core.security import generate_secure_api_key
from app.models.merchant import Merchant
from app.models.verification import VerificationSession, SessionStatus
from app.models.transaction import TransactionReceipt
from app.models.audit import AuditLog
from app.models.settings import PlatformSettings
from app.models.admin_extensions import FeatureFlag, DynamicParserRule, FraudRecord

router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])
security_scheme = HTTPBearer()

# --- SECURITY PROTECTION DEPENDENCY ---

async def verify_admin_auth(credentials: HTTPAuthorizationCredentials = Depends(security_scheme)) -> dict:
    """Enforces token boundaries to guarantee administrative operations remain highly insulated."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "admin_access" or not payload.get("is_superuser", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administrative elevation missing. Action prohibited."
            )
        return payload
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Administrative authorization credentials invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )

# --- PYDANTIC SCHEMAS ---

class MerchantUpdateSchema(BaseModel):
    name: Optional[str] = None
    payment_phone: Optional[str] = None
    is_active: Optional[bool] = None
    extend_subscription_days: Optional[int] = None

class ParserRuleConfigSchema(BaseModel):
    provider: str
    target_url_template: str
    selectors: dict[str, str]
    is_active: bool = True

class FeatureFlagToggleSchema(BaseModel):
    key: str
    description: Optional[str] = None
    is_enabled: bool

class PlatformSettingsUpdateSchema(BaseModel):
    monthly_fee: Optional[float] = Field(None, gt=0.0)
    receiver_phone: Optional[str] = None
    receiver_name: Optional[str] = None

# --- FEATURE 1: MERCHANT MANAGEMENT ---

@router.get("/merchants", dependencies=[Depends(verify_admin_auth)])
async def list_merchants(page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100), db: AsyncSession = Depends(get_db)):
    offset = (page - 1) * limit
    result = await db.execute(select(Merchant).order_by(Merchant.created_at.desc()).offset(offset).limit(limit))
    count_res = await db.execute(select(func.count(Merchant.id)))
    return {"total": count_res.scalar_one(), "data": result.scalars().all()}

@router.patch("/merchants/{merchant_id}", dependencies=[Depends(verify_admin_auth)])
async def modify_merchant(merchant_id: int, payload: MerchantUpdateSchema, db: AsyncSession = Depends(get_db)):
    query = await db.execute(select(Merchant).where(Merchant.id == merchant_id))
    merchant = query.scalar_one_or_none()
    if not merchant:
        raise HTTPException(status_code=404, detail="Target merchant not found.")
    
    if payload.name is not None: merchant.name = payload.name
    if payload.payment_phone is not None: merchant.payment_phone = payload.payment_phone
    if payload.is_active is not None: merchant.is_active = payload.is_active
    
    if payload.extend_subscription_days is not None:
        current_expiry = merchant.subscription_expires_at or datetime.now(timezone.utc)
        if current_expiry < datetime.now(timezone.utc):
            current_expiry = datetime.now(timezone.utc)
        merchant.subscription_expires_at = current_expiry + timedelta(days=payload.extend_subscription_days)

    db.add(AuditLog(action="ADMIN_MERCHANT_MODIFIED", entity_name="Merchant", entity_id=str(merchant_id), payload=payload.model_dump(exclude_none=True)))
    await db.commit()
    return {"status": "success", "merchant_id": merchant_id}

@router.post("/merchants/{merchant_id}/rotate-key", dependencies=[Depends(verify_admin_auth)])
async def reset_merchant_api_credentials(merchant_id: int, db: AsyncSession = Depends(get_db)):
    query = await db.execute(select(Merchant).where(Merchant.id == merchant_id))
    merchant = query.scalar_one_or_none()
    if not merchant:
        raise HTTPException(status_code=404, detail="Target merchant not found.")
    
    raw_key, key_hash = generate_secure_api_key()
    merchant.api_key_hash = key_hash
    
    db.add(AuditLog(action="ADMIN_API_KEY_ROTATED", entity_name="Merchant", entity_id=str(merchant_id), payload={"info": "API key hash systematically overridden via dashboard authorization."}))
    await db.commit()
    return {"status": "success", "new_raw_api_key": raw_key}

# --- FEATURE 2: SUBSCRIPTIONS ---

@router.get("/subscriptions/status", dependencies=[Depends(verify_admin_auth)])
async def track_subscriptions_summary(db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    active_query = await db.execute(select(func.count(Merchant.id)).where(and_(Merchant.subscription_expires_at > now, Merchant.is_active == True)))
    expired_query = await db.execute(select(func.count(Merchant.id)).where(or_(Merchant.subscription_expires_at <= now, Merchant.subscription_expires_at.is_(None))))
    return {"active_subscriptions": active_query.scalar_one(), "expired_or_inactive": expired_query.scalar_one()}

# --- FEATURE 3: TRANSACTIONS ---

@router.get("/transactions", dependencies=[Depends(verify_admin_auth)])
async def get_all_transactions(page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100), status_filter: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    offset = (page - 1) * limit
    stmt = select(TransactionReceipt)
    if status_filter:
        stmt = stmt.where(TransactionReceipt.transaction_status == status_filter)
    
    result = await db.execute(stmt.order_by(TransactionReceipt.created_at.desc()).offset(offset).limit(limit))
    return {"data": result.scalars().all()}

# --- FEATURE 4: PARSER MANAGEMENT ---

@router.post("/parser/rules", dependencies=[Depends(verify_admin_auth)])
async def upsert_parser_configuration(payload: ParserRuleConfigSchema, db: AsyncSession = Depends(get_db)):
    query = await db.execute(select(DynamicParserRule).where(DynamicParserRule.provider == payload.provider.lower()))
    rule = query.scalar_one_or_none()
    
    if rule:
        rule.target_url_template = payload.target_url_template
        rule.selectors = payload.selectors
        rule.version += 1
        rule.is_active = payload.is_active
    else:
        rule = DynamicParserRule(provider=payload.provider.lower(), target_url_template=payload.target_url_template, selectors=payload.selectors, is_active=payload.is_active)
        db.add(rule)
        
    db.add(AuditLog(action="ADMIN_PARSER_RULE_UPDATED", entity_name="DynamicParserRule", entity_id=payload.provider, payload=payload.model_dump()))
    await db.commit()
    return {"status": "success", "provider": payload.provider, "current_version": rule.version}

# --- FEATURE 5 & 6: SYSTEM LOGS & AUDIT LOGS ---

@router.get("/audit-logs", dependencies=[Depends(verify_admin_auth)])
async def query_system_audit_trail(page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=200), action_filter: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    offset = (page - 1) * limit
    stmt = select(AuditLog)
    if action_filter:
        stmt = stmt.where(AuditLog.action == action_filter)
        
    result = await db.execute(stmt.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit))
    return {"data": result.scalars().all()}

# --- FEATURE 7: FRAUD QUEUE ---

@router.get("/fraud-queue", dependencies=[Depends(verify_admin_auth)])
async def fetch_fraud_queue(unresolved_only: bool = True, db: AsyncSession = Depends(get_db)):
    stmt = select(FraudRecord)
    if unresolved_only:
        stmt = stmt.where(FraudRecord.is_resolved == False)
    result = await db.execute(stmt.order_by(FraudRecord.risk_score.desc()))
    return {"queue": result.scalars().all()}

@router.post("/fraud-queue/{record_id}/resolve", dependencies=[Depends(verify_admin_auth)])
async def resolve_fraud_incident(record_id: int, notes: str, db: AsyncSession = Depends(get_db)):
    query = await db.execute(select(FraudRecord).where(FraudRecord.id == record_id))
    record = query.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Incident context not found.")
    record.is_resolved = True
    record.resolution_notes = notes
    await db.commit()
    return {"status": "success", "record_id": record_id}

# --- FEATURE 8 & 9: ANALYTICS & REVENUE ---

@router.get("/analytics/dashboard", dependencies=[Depends(verify_admin_auth)])
async def process_platform_metrics(db: AsyncSession = Depends(get_db)):
    total_volume_res = await db.execute(select(func.sum(TransactionReceipt.settled_amount)))
    total_tx_count = await db.execute(select(func.count(TransactionReceipt.id)))
    verified_sessions = await db.execute(select(func.count(VerificationSession.id)).where(VerificationSession.status == SessionStatus.VERIFIED))
    
    # Financial metrics for platform onboarding fees
    onboarding_earnings = await db.execute(
        select(func.sum(TransactionReceipt.settled_amount))
        .join(VerificationSession, TransactionReceipt.session_id == VerificationSession.id)
        .where(VerificationSession.merchant_id == 1) # Master root merchant account references
    )

    return {
        "gross_financial_volume_etb": total_volume_res.scalar_one() or 0.0,
        "processed_receipts_count": total_tx_count.scalar_one(),
        "successful_sessions_count": verified_sessions.scalar_one(),
        "platform_collected_revenue_etb": onboarding_earnings.scalar_one() or 0.0
    }

# --- FEATURE 10: FEATURE FLAGS ---

@router.post("/feature-flags", dependencies=[Depends(verify_admin_auth)])
async def configure_feature_flag(payload: FeatureFlagToggleSchema, db: AsyncSession = Depends(get_db)):
    query = await db.execute(select(FeatureFlag).where(FeatureFlag.key == payload.key))
    flag = query.scalar_one_or_none()
    
    if flag:
        flag.is_enabled = payload.is_enabled
        if payload.description: flag.description = payload.description
    else:
        flag = FeatureFlag(key=payload.key, description=payload.description, is_enabled=payload.is_enabled)
        db.add(flag)
        
    await db.commit()
    return {"status": "success", "flag_key": payload.key, "is_enabled": flag.is_enabled}

# --- FEATURE 11: SYSTEM CONFIGURATION ---

@router.get("/configuration", dependencies=[Depends(verify_admin_auth)])
async def view_platform_monetization_settings(db: AsyncSession = Depends(get_db)):
    query = await db.execute(select(PlatformSettings).where(PlatformSettings.id == 1))
    return query.scalar_one_or_none()

@router.patch("/configuration", dependencies=[Depends(verify_admin_auth)])
async def update_platform_monetization_settings(payload: PlatformSettingsUpdateSchema, db: AsyncSession = Depends(get_db)):
    query = await db.execute(select(PlatformSettings).where(PlatformSettings.id == 1))
    config = query.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=500, detail="Base platform configurations are uninitialized.")
    
    if payload.monthly_fee is not None: config.monthly_fee = payload.monthly_fee
    if payload.receiver_phone is not None: config.receiver_phone = payload.receiver_phone
    if payload.receiver_name is not None: config.receiver_name = payload.receiver_name
    
    db.add(AuditLog(action="ADMIN_MONETIZATION_CONFIG_ALTERED", entity_name="PlatformSettings", entity_id="1", payload=payload.model_dump(exclude_none=True)))
    await db.commit()
    return {"status": "success", "updated_configuration": config}