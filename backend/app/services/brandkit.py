"""Phase 5 Track G — Brand kit lookups + propagation helpers."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brandkit import BrandKit
from app.models.media_asset import MediaAsset

DEFAULT_SUBTITLE_STYLE: dict[str, Any] = {
    "font_family": "Anton",
    "font_size_pct": 0.05,
    "color": "#FFFFFF",
    "outline_color": "#000000",
    "outline_width_px": 3,
    "background": "transparent",
    "position": "bottom",
    "uppercase": False,
    "word_highlight_color": "#FFD700",
}

DEFAULT_KIT: dict[str, Any] = {
    "primary_color": "#3050A0",
    "secondary_color": "#101018",
    "accent_color": "#FFD166",
    "font_heading": "Anton",
    "font_body": "Inter",
    "watermark_opacity": 0.6,
    "watermark_position": "bottom-right",
    "music_style_default": "ambient",
    "subtitle_style": DEFAULT_SUBTITLE_STYLE,
    "watermark_asset_path": None,
    "logo_asset_path": None,
}


async def load_brandkit(session: AsyncSession, user_id: uuid.UUID) -> dict[str, Any]:
    """Return a merged kit dict (DB → defaults). Always returns something usable."""
    row = (
        await session.execute(
            select(BrandKit).where(BrandKit.user_id == user_id)
        )
    ).scalar_one_or_none()
    if row is None:
        return dict(DEFAULT_KIT)

    kit = dict(DEFAULT_KIT)
    # Overlay non-null DB values
    for col in (
        "primary_color",
        "secondary_color",
        "accent_color",
        "font_heading",
        "font_body",
        "music_style_default",
        "watermark_position",
    ):
        v = getattr(row, col)
        if v is not None:
            kit[col] = v
    if row.watermark_opacity is not None:
        kit["watermark_opacity"] = float(row.watermark_opacity)
    if isinstance(row.subtitle_style, dict) and row.subtitle_style:
        merged = dict(DEFAULT_SUBTITLE_STYLE)
        merged.update(row.subtitle_style)
        kit["subtitle_style"] = merged

    # Resolve asset paths
    async def _resolve(asset_id: uuid.UUID | None) -> str | None:
        if asset_id is None:
            return None
        a = (
            await session.execute(
                select(MediaAsset).where(MediaAsset.id == asset_id)
            )
        ).scalar_one_or_none()
        return a.file_path if a else None

    kit["logo_asset_path"] = await _resolve(row.logo_asset_id)
    kit["watermark_asset_path"] = await _resolve(row.watermark_asset_id)
    return kit


def og_palette(kit: dict[str, Any]) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    """Return (bg, accent) RGB tuples for OG thumbnail rendering."""

    def _hex(s: str, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
        s = (s or "").lstrip("#")
        if len(s) == 6:
            try:
                return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
            except ValueError:
                pass
        return fallback

    bg = _hex(kit.get("secondary_color") or "#101018", (16, 16, 24))
    accent = _hex(kit.get("primary_color") or "#3050A0", (80, 100, 220))
    return bg, accent
