from datetime import datetime, timedelta, timezone
import jwt
import secrets
from typing import Tuple, Optional
import hashlib
from app.core.config import settings
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from app.core.database import get_db
from app.models.merchant import Merchant

# Setup secure header parsing for API keys
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=True)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "token_type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "token_type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def generate_secure_api_key() -> Tuple[str, str, str]:
    """Generates a raw key, its DB hash, and a visible prefix."""
    raw_key = f"pvp_{secrets.token_urlsafe(32)}"
    prefix = raw_key[:12]
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, key_hash, prefix

def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()

async def verify_merchant_api_key(
    api_key: str = Security(API_KEY_HEADER),
    db: AsyncSession = Depends(get_db)
) -> Merchant:
    """
    Dependency injector to enforce API key matching for programmatic merchant access.
    Hashes incoming keys and checks them against the immutable storage records.
    """
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    result = await db.execute(
        select(Merchant).where(
            Merchant.api_key_hash == api_key_hash,
            Merchant.is_active == True
        )
    )
    merchant = result.scalar_one_or_none()
    
    if not merchant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: Invalid or inactive API Key provider credentials."
        )
    return merchant

def create_verification_token(session_id: str, expected_amount: float) -> str:
    """Creates a signed JWT containing session requirements."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=15) # Configurable expiration
    to_encode = {
        "sub": session_id,
        "exp": expire,
        "amt": expected_amount,
        "type": "verification_session"
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

security_scheme = HTTPBearer()

async def verify_merchant_auth(credentials: HTTPAuthorizationCredentials = Depends(security_scheme)) -> dict:
    """
    Secures upstream administrative endpoints (like session generation).
    Expects a valid Bearer token in the HTTP Authorization header.
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "merchant_access":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid token scope. Access denied."
            )
        return payload
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials or token expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )