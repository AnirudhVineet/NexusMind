"""Phase 5 Track G — BrandKit ORM."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Numeric, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BrandKit(Base):
    __tablename__ = "brand_kits"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    primary_color: Mapped[str | None] = mapped_column(Text, nullable=True)
    secondary_color: Mapped[str | None] = mapped_column(Text, nullable=True)
    accent_color: Mapped[str | None] = mapped_column(Text, nullable=True)
    font_heading: Mapped[str | None] = mapped_column(Text, nullable=True)
    font_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("media_assets.id", ondelete="SET NULL"),
        nullable=True,
    )
    watermark_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("media_assets.id", ondelete="SET NULL"),
        nullable=True,
    )
    watermark_opacity: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), nullable=False, server_default=text("0.6")
    )
    watermark_position: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'bottom-right'")
    )
    music_style_default: Mapped[str | None] = mapped_column(Text, nullable=True)
    subtitle_style: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
