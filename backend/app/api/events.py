"""User event tracking endpoints — Phase 4 Personal Memory Layer.

POST /api/events — record a user interaction event
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.exceptions import ValidationError
from app.db.session import get_session
from app.models.user import User
from app.models.user_event import ALLOWED_EVENT_TYPES, UserEvent

router = APIRouter(prefix="/api", tags=["events"])


# ─── schemas ──────────────────────────────────────────────────────────────────

class EventCreate(BaseModel):
    event_type: str
    target_type: str | None = None
    target_id: uuid.UUID | None = None
    metadata: dict = {}


# ─── create event ─────────────────────────────────────────────────────────────

@router.post("/events", status_code=status.HTTP_200_OK)
async def create_event(
    body: EventCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if body.event_type not in ALLOWED_EVENT_TYPES:
        raise ValidationError(
            f"Invalid event_type. Allowed: {', '.join(ALLOWED_EVENT_TYPES)}"
        )

    event = UserEvent(
        user_id=current_user.id,
        event_type=body.event_type,
        target_type=body.target_type,
        target_id=body.target_id,
        event_metadata=body.metadata,
    )
    session.add(event)
    await session.commit()

    return {"status": "ok"}
