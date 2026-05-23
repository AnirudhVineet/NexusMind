"""SQLAlchemy models for RSS feed ingestion — Phase 4 Track F."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RssFeed(Base):
    """A user-subscribed RSS/Atom feed that is polled on a schedule."""

    __tablename__ = "rss_feeds"
    __table_args__ = (
        Index("idx_rss_feeds_user", "user_id", "enabled"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default=text("''"),
    )
    interval_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=360,
        server_default=text("360"),
    )
    last_fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_etag: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_modified: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    seen_items = relationship(
        "RssSeenItem", back_populates="feed", cascade="all, delete-orphan"
    )


class RssSeenItem(Base):
    """Deduplication table — tracks GUIDs already ingested from each feed."""

    __tablename__ = "rss_seen_items"

    feed_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rss_feeds.id", ondelete="CASCADE"),
        primary_key=True,
    )
    item_guid: Mapped[str] = mapped_column(Text, primary_key=True, nullable=False)
    seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

    feed = relationship("RssFeed", back_populates="seen_items")
