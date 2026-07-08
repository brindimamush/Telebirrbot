# app/services/merchant_platform.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from pydantic import BaseModel
from typing import List, Optional

from app.core.database import get_db
from app.core.security import generate_secure_api_key
from app.models.auth import MerchantAPIKey
from app.models.audit import AuditLog
# Assume dependencies have a `get_current_merchant_dashboard_user` similar to the admin one
# For demonstration, simulating the merchant injection
from app.core.dependencies import get_current_admin # Placeholder: Replace with Merchant JWT auth

router = APIRouter(prefix="/merchant/platform", tags=["Merchant Platform"])

class APIKeyCreate(BaseModel):
    name: str
    ip_whitelist: Optional[List[str]] = None

@router.post("/api-keys")
async def create_api_key(req: APIKeyCreate, merchant_id: int, db: AsyncSession = Depends(get_db)):
    raw_key, key_hash, prefix = generate_secure_api_key()
    
    new_key = MerchantAPIKey(
        merchant_id=merchant_id,
        name=req.name,
        prefix=prefix,
        key_hash=key_hash,
        ip_whitelist=req.ip_whitelist
    )
    db.add(new_key)
    db.add(AuditLog(action="API_KEY_CREATED", entity_name="MerchantAPIKey", entity_id=str(merchant_id), payload={"name": req.name}))
    await db.commit()
    
    return {"status": "success", "raw_key": raw_key, "prefix": prefix} # Raw key shown ONLY once

@router.post("/api-keys/{key_id}/rotate")
async def rotate_api_key(key_id: int, merchant_id: int, db: AsyncSession = Depends(get_db)):
    """Invalidates the old key and generates a new one instantly."""
    result = await db.execute(select(MerchantAPIKey).where(MerchantAPIKey.id == key_id, MerchantAPIKey.merchant_id == merchant_id))
    old_key = result.scalar_one_or_none()
    
    if not old_key:
        raise HTTPException(status_code=404, detail="API Key not found")

    old_key.is_active = False # Disable old key
    
    raw_key, key_hash, prefix = generate_secure_api_key()
    new_key = MerchantAPIKey(
        merchant_id=merchant_id,
        name=f"{old_key.name} (Rotated)",
        prefix=prefix,
        key_hash=key_hash,
        ip_whitelist=old_key.ip_whitelist
    )
    db.add(new_key)
    db.add(AuditLog(action="API_KEY_ROTATED", entity_name="MerchantAPIKey", entity_id=str(key_id), payload={"new_prefix": prefix}))
    await db.commit()
    
    return {"status": "success", "new_raw_key": raw_key, "new_prefix": prefix}