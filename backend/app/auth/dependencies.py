import uuid

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import decode_token
from app.core.exceptions import AuthError
from app.db.session import get_session
from app.models.user import User


async def _resolve_user(authorization: str | None, session: AsyncSession) -> tuple[User, dict]:
    if not authorization:
        raise AuthError("Missing Authorization header")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthError("Invalid Authorization header")

    payload = decode_token(parts[1])
    sub = payload.get("sub")
    if not sub:
        raise AuthError("Invalid token payload")

    try:
        user_id = uuid.UUID(sub)
    except ValueError as e:
        raise AuthError("Invalid token subject") from e

    user = (
        await session.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()

    if user is None:
        raise AuthError("User not found")

    return user, payload


async def get_current_user(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> User:
    user, _ = await _resolve_user(authorization, session)
    return user
