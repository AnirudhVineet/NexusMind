"""Phase 5 Track H — Quota + cost surfacing for the Studio header."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.services.media.quota import all_quota_status

router = APIRouter(prefix="/api/media", tags=["quota"])


@router.get("/quota-status")
async def quota_status(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await all_quota_status(session, user.id)
