"""User voice preferences + brief narration chapters — Phase 5 Track B."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserVoicePreference(Base):
    __tablename__ = "user_voice_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    default_voice_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    speed: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), nullable=False, server_default=text("1.0")
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class BriefNarration(Base):
    __tablename__ = "brief_narrations"
    __table_args__ = (Index("idx_brief_narrations_brief", "brief_id"),)

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
    brief_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_briefs.id", ondelete="CASCADE"),
        nullable=False,
    )
    media_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("media_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    # List of { heading, text, offset_seconds, duration_seconds }
    chapters: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    voice_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    speed: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
