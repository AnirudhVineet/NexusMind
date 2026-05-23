"""SQLAlchemy model for AI-generated repurposed content (Track H)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SOURCE_TYPES = ["document", "topic", "entity", "chunk"]
CONTENT_TYPES = ["reel_script", "meme", "thread", "storyboard", "caption"]
STYLES = ["educational", "humorous", "viral", "professional"]


class GeneratedContent(Base):
    """A single piece of AI-repurposed content derived from a knowledge source."""

    __tablename__ = "generated_content"
    __table_args__ = (
        Index("idx_generated_content_user", "user_id", "created_at"),
        Index("idx_generated_content_source", "user_id", "source_id"),
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
    # One of SOURCE_TYPES
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    # One of CONTENT_TYPES
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    # One of STYLES
    style: Mapped[str] = mapped_column(Text, nullable=False)
    # The structured generated output
    content_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    # Snapshot of source chunk dicts used during generation
    source_chunks: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    # List of fidelity check results per claim/beat
    fidelity_flags: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    # Absolute path to a rendered file (e.g. meme PNG)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    # queued / running / complete / failed
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'queued'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )
    edited_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
