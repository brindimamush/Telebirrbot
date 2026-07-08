# app/core/dependencies.py
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import jwt
from app.core.config import settings
from app.core.database import get_db
from app.core.security import hash_api_key
from app.models.auth import AdminUser, MerchantAPIKey, AdminRole
from app.models.merchant import Merchant
import ipaddress

security_scheme = HTTPBearer()
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_db)
) -> AdminUser:
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("token_type") != "access" or "admin_id" not in payload:
            raise ValueError()
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    result = await db.execute(select(AdminUser).where(AdminUser.id == payload["admin_id"]))
    admin = result.scalar_one_or_none()
    if not admin or not admin.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin inactive or deleted")
    return admin

class RoleChecker:
    def __init__(self, allowed_roles: list[AdminRole]):
        self.allowed_roles = allowed_roles

    def __call__(self, admin: AdminUser = Depends(get_current_admin)):
        if admin.role not in self.allowed_roles and admin.role != AdminRole.SUPERADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return admin

async def verify_merchant_api_key(
    request: Request,
    api_key: str = Depends(api_key_header),
    db: AsyncSession = Depends(get_db)
) -> Merchant:
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API Key")
    
    hashed_key = hash_api_key(api_key)
    result = await db.execute(
        select(MerchantAPIKey, Merchant)
        .join(Merchant, MerchantAPIKey.merchant_id == Merchant.id)
        .where(MerchantAPIKey.key_hash == hashed_key, MerchantAPIKey.is_active == True)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or inactive API Key")
    
    api_key_record, merchant = row

    # IP Whitelist Validation
    if api_key_record.ip_whitelist:
        client_ip = request.client.host
        allowed = any(ipaddress.ip_address(client_ip) in ipaddress.ip_network(net, strict=False) for net in api_key_record.ip_whitelist)
        if not allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="IP address not authorized")

    if not merchant.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Merchant account suspended")

    return merchant