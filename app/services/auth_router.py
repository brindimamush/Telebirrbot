# app/services/auth_router.py
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
import jwt

from app.core.database import get_db
from app.core.security import verify_password, create_access_token, create_refresh_token
from app.core.config import settings
from app.models.auth import AdminUser, LoginHistory, DeviceRegistration

router = APIRouter(prefix="/auth", tags=["Authentication"])

class LoginRequest(BaseModel):
    email: str
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str

class DeviceRegisterRequest(BaseModel):
    merchant_id: int
    device_fingerprint: str
    hardware_id: str

@router.post("/admin/login")
async def admin_login(req: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AdminUser).where(AdminUser.email == req.email))
    admin = result.scalar_one_or_none()
    
    client_ip = request.client.host
    user_agent = request.headers.get("user-agent")

    if not admin or not verify_password(req.password, admin.hashed_password):
        if admin:
            db.add(LoginHistory(user_id=admin.id, user_type="ADMIN", ip_address=client_ip, user_agent=user_agent, status="FAILED"))
            await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    db.add(LoginHistory(user_id=admin.id, user_type="ADMIN", ip_address=client_ip, user_agent=user_agent, status="SUCCESS"))
    await db.commit()

    access_token = create_access_token(data={"admin_id": admin.id, "role": admin.role})
    refresh_token = create_refresh_token(data={"admin_id": admin.id})
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

@router.post("/refresh")
async def refresh_session(req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = jwt.decode(req.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("token_type") != "refresh":
            raise ValueError()
        
        # Verify user still exists and is active
        admin_id = payload["admin_id"]
        result = await db.execute(select(AdminUser).where(AdminUser.id == admin_id))
        admin = result.scalar_one_or_none()
        if not admin or not admin.is_active:
            raise ValueError()

        new_access = create_access_token(data={"admin_id": admin.id, "role": admin.role})
        return {"access_token": new_access, "token_type": "bearer"}
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

@router.post("/device/register")
async def register_device(req: DeviceRegisterRequest, db: AsyncSession = Depends(get_db)):
    """Called by the Flutter app after PlayIntegrity checks pass."""
    device = DeviceRegistration(
        merchant_id=req.merchant_id,
        device_fingerprint=req.device_fingerprint,
        hardware_id=req.hardware_id
    )
    db.add(device)
    await db.commit()
    return {"status": "success", "device_id": device.id}