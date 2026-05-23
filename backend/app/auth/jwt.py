import time
import uuid
from typing import Any

import jwt

from app.core.config import get_settings
from app.core.exceptions import AuthError

settings = get_settings()


def create_access_token(user_id: uuid.UUID, email: str) -> tuple[str, int]:
    now = int(time.time())
    exp = now + settings.jwt_expiry_seconds
    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": now,
        "exp": exp,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, settings.jwt_expiry_seconds


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError as e:
        raise AuthError("Token expired") from e
    except jwt.InvalidTokenError as e:
        raise AuthError("Invalid token") from e
