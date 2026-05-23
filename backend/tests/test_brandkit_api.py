"""Track G — brandkit defaults + palette helpers."""
from __future__ import annotations

from app.services.brandkit import (
    DEFAULT_KIT,
    DEFAULT_SUBTITLE_STYLE,
    og_palette,
)


def test_default_kit_has_required_keys():
    for key in (
        "primary_color",
        "secondary_color",
        "accent_color",
        "font_heading",
        "font_body",
        "watermark_opacity",
        "watermark_position",
        "music_style_default",
        "subtitle_style",
    ):
        assert key in DEFAULT_KIT


def test_default_subtitle_style_shape():
    for key in (
        "font_family",
        "font_size_pct",
        "color",
        "outline_color",
        "outline_width_px",
        "position",
    ):
        assert key in DEFAULT_SUBTITLE_STYLE


def test_og_palette_parses_hex_colors():
    kit = {"secondary_color": "#0F1020", "primary_color": "#80A0FF"}
    bg, accent = og_palette(kit)
    assert bg == (15, 16, 32)
    assert accent == (128, 160, 255)


def test_og_palette_falls_back_on_invalid_hex():
    kit = {"secondary_color": "not-hex", "primary_color": ""}
    bg, accent = og_palette(kit)
    assert isinstance(bg, tuple) and len(bg) == 3
    assert isinstance(accent, tuple) and len(accent) == 3
