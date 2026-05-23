"""Phase 5 Track C — Region-driven meme renderer.

Reads sidecar JSON descriptors from
`backend/app/assets/meme_templates/sidecars.py` and overlays text onto the
template PNG using Pillow. Falls back to a single centered region when the
template has no descriptor.

For `template_name = "custom"`, renders an AI-generated background via
`visual_provider.generate_visual` and stamps text on top.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Optional

from app.core.logging import get_logger
from app.services.media import memes_dir
from app.services.media.visual_provider import generate_visual

log = get_logger(__name__)

ASSETS_DIR = Path(__file__).parent.parent.parent / "assets"
TEMPLATES_DIR = ASSETS_DIR / "meme_templates"
FONT_DIR = ASSETS_DIR / "fonts"


def _font_paths() -> list[str]:
    """Candidate font paths in order of preference."""
    candidates: list[Path] = []
    if FONT_DIR.exists():
        for name in ("Anton-Regular.ttf", "Impact.ttf"):
            candidates.append(FONT_DIR / name)
    # System fonts
    candidates.extend(
        [
            Path("C:/Windows/Fonts/Anton-Regular.ttf"),
            Path("C:/Windows/Fonts/impact.ttf"),
            Path("C:/Windows/Fonts/Impact.ttf"),
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("C:/Windows/Fonts/Arial.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ]
    )
    return [str(p) for p in candidates if p.exists()]


def _load_font(size: int):
    from PIL import ImageFont

    for path in _font_paths():
        try:
            return ImageFont.truetype(path, size)
        except (OSError, ValueError):
            continue
    return ImageFont.load_default()


def _hex_to_rgba(s: str) -> tuple[int, int, int, int]:
    s = s.strip().lstrip("#")
    if len(s) == 6:
        s = s + "FF"
    if len(s) != 8:
        return (255, 255, 255, 255)
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), int(s[6:8], 16))


def _wrap_text_to_box(
    draw,
    text: str,
    font,
    max_width: int,
    max_height: int,
) -> list[str]:
    """Greedy word-wrap so each line fits in max_width, dropping lines beyond max_height."""
    if not text:
        return []
    words = text.split()
    if not words:
        return []

    lines: list[str] = []
    cur = words[0]
    for w in words[1:]:
        candidate = cur + " " + w
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_width:
            cur = candidate
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)

    # Drop lines that overflow max_height
    line_height = font.size + 4
    max_lines = max(1, max_height // line_height)
    return lines[:max_lines]


def _draw_region(draw, img, text: str, region: dict[str, Any]) -> None:
    if not text or not text.strip():
        return

    w, h = img.size
    rx = int(region["x"] * w)
    ry = int(region["y"] * h)
    rw = int(region["w"] * w)
    rh = int(region["h"] * h)
    align = region.get("align", "center")
    font_size_pct = float(region.get("font_size_pct", 0.05))
    font_size = max(14, int(h * font_size_pct))
    uppercase = bool(region.get("uppercase", False))
    alternate_caps = bool(region.get("alternate_caps", False))

    if uppercase:
        text = text.upper()
    elif alternate_caps:
        text = "".join(c.upper() if i % 2 else c.lower() for i, c in enumerate(text))

    color = _hex_to_rgba(region.get("color", "#FFFFFFFF"))
    outline_hex = region.get("outline", "")
    outline = _hex_to_rgba(outline_hex) if outline_hex else None

    # Shrink-to-fit: reduce font size if text won't wrap into the box
    font = _load_font(font_size)
    while font_size > 12:
        font = _load_font(font_size)
        lines = _wrap_text_to_box(draw, text, font, rw, rh)
        # Re-measure total height
        total_h = (font.size + 4) * len(lines)
        widest = max(
            (draw.textbbox((0, 0), ln, font=font)[2] for ln in lines), default=0
        )
        if total_h <= rh and widest <= rw:
            break
        font_size = int(font_size * 0.92)
    else:
        lines = _wrap_text_to_box(draw, text, font, rw, rh)

    if not lines:
        return

    line_height = font.size + 4
    total_h = line_height * len(lines)
    y = ry + max(0, (rh - total_h) // 2)

    for ln in lines:
        bbox = draw.textbbox((0, 0), ln, font=font)
        line_w = bbox[2] - bbox[0]
        if align == "left":
            x = rx
        elif align == "right":
            x = rx + rw - line_w
        else:
            x = rx + (rw - line_w) // 2

        # Outline first, then fill — produces a clean classic meme look
        if outline is not None:
            for dx in (-2, -1, 0, 1, 2):
                for dy in (-2, -1, 0, 1, 2):
                    if dx == 0 and dy == 0:
                        continue
                    draw.text((x + dx, y + dy), ln, font=font, fill=outline)
        draw.text((x, y), ln, font=font, fill=color)
        y += line_height


# ─── Public entry points ────────────────────────────────────────────────────


def render_meme(
    template_key: str,
    panel_texts: dict[str, str],
    *,
    out_path: Optional[Path] = None,
) -> Optional[Path]:
    """Render a meme PNG by overlaying `panel_texts` onto a template.

    `panel_texts` is keyed by region id. Missing regions are skipped silently.
    Returns the absolute output path on success, None on failure.

    Falls back to compatibility behaviour: if the caller still uses the legacy
    {"top": ..., "bottom": ...} shape on a template whose sidecar declares
    "aliases", we map top/bottom onto the first two region ids.
    """
    try:
        from PIL import Image, ImageDraw

        from app.assets.meme_templates.sidecars import get_sidecar

        side = get_sidecar(template_key)
        if not side:
            log.warning("meme_renderer.no_sidecar", template=template_key)
            return None

        # Resolve filename and existence
        normalized = template_key.lower().replace(" ", "_")
        template_path = TEMPLATES_DIR / f"{normalized}.png"
        if not template_path.exists():
            # Final fallback to drake
            template_path = TEMPLATES_DIR / "drake.png"
            if not template_path.exists():
                return None
            side = get_sidecar("drake") or side

        img = Image.open(template_path).convert("RGBA")
        draw = ImageDraw.Draw(img)

        # Compatibility: map legacy top/bottom keys when the sidecar lists them
        if "aliases" in side and ("top" in panel_texts or "bottom" in panel_texts):
            regions = side["regions"]
            if "top" in panel_texts and regions:
                panel_texts.setdefault(regions[0]["id"], panel_texts["top"])
            if "bottom" in panel_texts and len(regions) > 1:
                panel_texts.setdefault(regions[1]["id"], panel_texts["bottom"])

        for region in side["regions"]:
            text = panel_texts.get(region["id"], "")
            _draw_region(draw, img, text, region)

        if out_path is None:
            out_path = memes_dir() / f"{uuid.uuid4()}.png"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img.convert("RGB").save(str(out_path), format="PNG")
        return out_path
    except Exception as e:
        log.exception("meme_renderer.render_failed", error=str(e))
        return None


async def render_custom_meme(
    main_text: str,
    background_prompt: str,
    *,
    out_path: Optional[Path] = None,
) -> Optional[Path]:
    """Render a meme on top of an AI-generated background image."""
    try:
        from PIL import Image, ImageDraw

        from app.assets.meme_templates.sidecars import get_sidecar

        side = get_sidecar("custom")
        if not side:
            return None

        bg_path, _provider = await generate_visual(background_prompt, "square")
        img = Image.open(bg_path).convert("RGBA")
        # Resize to square 1080 for predictable text placement
        img = img.resize((1080, 1080))
        draw = ImageDraw.Draw(img)
        _draw_region(draw, img, main_text, side["regions"][0])
        if out_path is None:
            out_path = memes_dir() / f"{uuid.uuid4()}.png"
        img.convert("RGB").save(str(out_path), format="PNG")
        return out_path
    except Exception as e:
        log.exception("meme_renderer.custom_failed", error=str(e))
        return None


def list_templates() -> list[dict[str, Any]]:
    """Return metadata for every known template (sidecar + preview path)."""
    from app.assets.meme_templates.sidecars import list_templates as _list

    out: list[dict[str, Any]] = []
    for entry in _list():
        normalized = entry["key"]
        png = TEMPLATES_DIR / f"{normalized}.png"
        entry["has_image"] = png.exists()
        out.append(entry)
    return out
