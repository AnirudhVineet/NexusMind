"""SQLAlchemy model for media assets (images / audio / templates) — Phase 5 Track A."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, Numeric, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

ASSET_TYPES = [
    "image",
    "video_clip",
    "audio_clip",
    "music",
    "template",
    "brand_logo",
    "brand_watermark",
    "user_upload",
]
SOURCE_KINDS = ["generated", "stock", "uploaded", "brandkit", "bundled"]
LICENSES = ["cc0", "royalty_free", "user_owned", "api_terms", "fair_use_meme"]


class MediaAsset(Base):
    __tablename__ = "media_assets"
    __table_args__ = (
        Index(
            "idx_media_assets_user_type",
            "user_id",
            "asset_type",
            text("created_at DESC"),
        ),
        Index("idx_media_assets_source_ref", "source_ref"),
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
    asset_type: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    duration_seconds: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 3), nullable=True
    )
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_kind: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    license: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
