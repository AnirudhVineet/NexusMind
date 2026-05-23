"""Notifications management API — Phase 4 Track G.

GET    /api/notifications                  — list notifications (filterable)
POST   /api/notifications/{id}/read        — mark one as read
POST   /api/notifications/read-all         — mark all as read
DELETE /api/notifications/{id}             — dismiss / delete a notification
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.exceptions import NotFoundError
from app.db.session import get_session
from app.models.alert import Notification
from app.models.user import User

router = APIRouter(prefix="/api", tags=["notifications"])


# ─── schemas ──────────────────────────────────────────────────────────────────

class NotificationOut(BaseModel):
    id: uuid.UUID
    title: str
    body: str
    link: str
    read_at: datetime | None
    dismissed_at: datetime | None
    created_at: datetime
    metadata: dict[str, Any]

    model_config = {"from_attributes": True}


def _serialize(notif: Notification) -> NotificationOut:
    return NotificationOut(
        id=notif.id,
        title=notif.title,
        body=notif.body,
        link=notif.link or "",
        read_at=notif.read_at,
        dismissed_at=notif.dismissed_at,
        created_at=notif.created_at,
        metadata=notif.metadata_ or {},
    )


class NotificationListResponse(BaseModel):
    items: list[NotificationOut]
    total: int
    unread_count: int


# ─── endpoints ────────────────────────────────────────────────────────────────

@router.get("/notifications", response_model=NotificationListResponse)
async def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> NotificationListResponse:
    base = select(Notification).where(Notification.user_id == current_user.id)
    if unread_only:
        base = base.where(Notification.read_at.is_(None))

    total = (
        await session.execute(
            select(func.count(Notification.id))
            .where(Notification.user_id == current_user.id)
            .where(Notification.read_at.is_(None) if unread_only else True)
        )
    ).scalar_one()

    unread_count = (
        await session.execute(
            select(func.count(Notification.id)).where(
                Notification.user_id == current_user.id,
                Notification.read_at.is_(None),
            )
        )
    ).scalar_one()

    q = base.order_by(Notification.created_at.desc()).limit(limit).offset(offset)
    notifications = (await session.execute(q)).scalars().all()

    return NotificationListResponse(
        items=[_serialize(n) for n in notifications],
        total=int(total or 0),
        unread_count=int(unread_count or 0),
    )


@router.post("/notifications/{notification_id}/read", response_model=NotificationOut)
async def mark_notification_read(
    notification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> NotificationOut:
    notif = (
        await session.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if notif is None:
        raise NotFoundError("Notification not found")

    if notif.read_at is None:
        notif.read_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(notif)

    return _serialize(notif)


@router.post("/notifications/read-all")
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, int]:
    now = datetime.now(timezone.utc)
    result = await session.execute(
        update(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.read_at.is_(None),
        )
        .values(read_at=now)
    )
    await session.commit()
    return {"count": result.rowcount}


@router.delete("/notifications/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    notif = (
        await session.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if notif is None:
        raise NotFoundError("Notification not found")

    await session.delete(notif)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
