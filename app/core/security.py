from datetime import datetime, timedelta, timezone
import jwt
import secrets
import hashlib
from app.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from app.core.database import get_db
from app.models.merchant import Merchant

# Setup secure header parsing for API keys
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=True)

def generate_secure_api_key() -> tuple[str, str]:
    """
    Generates a raw secure API key for the merchant and its SHA-256 storage hash.
    Returns: (raw_key, key_hash)
    """
    raw_key = f"pvp_live_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, key_hash

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