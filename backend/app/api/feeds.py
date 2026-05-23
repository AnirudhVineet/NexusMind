"""RSS Feeds API — Phase 4 Track F.

CRUD for RSS/Atom feed subscriptions and a manual poll-now endpoint.

GET    /api/feeds              — list feeds
POST   /api/feeds              — subscribe to a feed
GET    /api/feeds/{id}         — get feed
PATCH  /api/feeds/{id}         — update feed
DELETE /api/feeds/{id}         — delete feed (204)
POST   /api/feeds/{id}/poll-now — queue an immediate poll
"""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.exceptions import NotFoundError
from app.db.session import get_session
from app.models.rss_feed import RssFeed
from app.models.user import User

router = APIRouter(prefix="/api", tags=["feeds"])


# ─── Pydantic schemas ──────────────────────────────────────────────────────────


class FeedCreate(BaseModel):
    url: str
    title: str = ""
    interval_minutes: int = 360


class FeedUpdate(BaseModel):
    url: str | None = None
    title: str | None = None
    interval_minutes: int | None = None
    enabled: bool | None = None


class FeedOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    url: str
    title: str
    interval_minutes: int
    last_fetched_at: datetime | None
    last_etag: str | None
    last_modified: str | None
    enabled: bool


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _feed_out(feed: RssFeed) -> FeedOut:
    return FeedOut(
        id=feed.id,
        user_id=feed.user_id,
        url=feed.url,
        title=feed.title,
        interval_minutes=feed.interval_minutes,
        last_fetched_at=feed.last_fetched_at,
        last_etag=feed.last_etag,
        last_modified=feed.last_modified,
        enabled=feed.enabled,
    )


async def _get_owned_feed(
    feed_id: uuid.UUID,
    user: User,
    session: AsyncSession,
) -> RssFeed:
    feed = (
        await session.execute(
            select(RssFeed).where(
                RssFeed.id == feed_id,
                RssFeed.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if feed is None:
        raise NotFoundError("Feed not found")
    return feed


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/feeds", response_model=list[FeedOut])
async def list_feeds(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[FeedOut]:
    rows = (
        await session.execute(
            select(RssFeed)
            .where(RssFeed.user_id == current_user.id)
            .order_by(RssFeed.id)
        )
    ).scalars().all()
    return [_feed_out(f) for f in rows]


@router.post("/feeds", status_code=status.HTTP_201_CREATED, response_model=FeedOut)
async def create_feed(
    body: FeedCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FeedOut:
    feed = RssFeed(
        user_id=current_user.id,
        url=body.url,
        title=body.title,
        interval_minutes=body.interval_minutes,
    )
    session.add(feed)
    await session.commit()
    await session.refresh(feed)
    return _feed_out(feed)


@router.get("/feeds/{feed_id}", response_model=FeedOut)
async def get_feed(
    feed_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FeedOut:
    feed = await _get_owned_feed(feed_id, current_user, session)
    return _feed_out(feed)


@router.patch("/feeds/{feed_id}", response_model=FeedOut)
async def update_feed(
    feed_id: uuid.UUID,
    body: FeedUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FeedOut:
    feed = await _get_owned_feed(feed_id, current_user, session)

    if body.url is not None:
        feed.url = body.url
    if body.title is not None:
        feed.title = body.title
    if body.interval_minutes is not None:
        feed.interval_minutes = body.interval_minutes
    if body.enabled is not None:
        feed.enabled = body.enabled

    await session.commit()
    await session.refresh(feed)
    return _feed_out(feed)


@router.delete(
    "/feeds/{feed_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_feed(
    feed_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    feed = await _get_owned_feed(feed_id, current_user, session)
    await session.delete(feed)
    await session.commit()


@router.post("/feeds/{feed_id}/poll-now")
async def poll_feed_now(
    feed_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Queue an immediate fetch of this feed."""
    feed = await _get_owned_feed(feed_id, current_user, session)
    from app.workers.celery_app import celery_app

    celery_app.send_task("fetch_rss_feed", args=[str(feed.id)], queue="default")
    return {"status": "queued"}
