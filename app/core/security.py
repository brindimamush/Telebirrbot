from datetime import datetime, timedelta, timezone
import jwt
from app.core.config import settings

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