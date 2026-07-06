from datetime import datetime, timedelta, timezone
import jwt
from app.core.config import settings
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

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