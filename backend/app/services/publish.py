"""Phase 5 Track F — Publishing pipeline.

Responsibilities:
  • create_share_link  — mint a slug, optionally with password + expiry
  • render_public_data — sanitized JSON for a public viewer
  • bundle_export      — zip up all formats for a content/media row
  • og_thumbnail       — synthesize a 1200x630 OG image
"""
from __future__ import annotations

import hashlib
import io
import secrets
import string
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.generated_content import GeneratedContent
from app.models.media_job import MediaJob
from app.models.research_brief import ResearchBrief
from app.models.share_link import ShareLink
from app.services.media import bundles_dir

log = get_logger(__name__)

SLUG_ALPHABET = string.ascii_letters + string.digits + "_-"
SLUG_LEN = 12


def generate_slug() -> str:
    return "".join(secrets.choice(SLUG_ALPHABET) for _ in range(SLUG_LEN))


def hash_password(plain: str) -> str:
    salt = secrets.token_hex(8)
    h = hashlib.sha256((salt + plain).encode("utf-8")).hexdigest()
    return f"{salt}${h}"


def verify_password(plain: str, hashed: str) -> bool:
    try:
        salt, h = hashed.split("$", 1)
    except ValueError:
        return False
    return hashlib.sha256((salt + plain).encode("utf-8")).hexdigest() == h


async def create_share_link(
    *,
    session: AsyncSession,
    user_id: uuid.UUID,
    target_type: str,
    target_id: uuid.UUID,
    expires_at: Optional[datetime] = None,
    password: Optional[str] = None,
    max_retries: int = 5,
) -> ShareLink:
    for _ in range(max_retries):
        slug = generate_slug()
        link = ShareLink(
            user_id=user_id,
            target_type=target_type,
            target_id=target_id,
            slug=slug,
            password_hash=hash_password(password) if password else None,
            expires_at=expires_at,
        )
        session.add(link)
        try:
            await session.commit()
            await session.refresh(link)
            return link
        except IntegrityError:
            await session.rollback()
            continue
    raise RuntimeError("Could not generate a unique slug after 5 retries")


async def resolve_link(
    session: AsyncSession, slug: str
) -> Optional[ShareLink]:
    row = (
        await session.execute(select(ShareLink).where(ShareLink.slug == slug))
    ).scalar_one_or_none()
    if row is None or not row.enabled:
        return None
    if row.expires_at and row.expires_at < datetime.now(timezone.utc):
        return None
    return row


async def record_view(session: AsyncSession, link: ShareLink) -> None:
    link.view_count = (link.view_count or 0) + 1
    link.last_viewed_at = datetime.now(timezone.utc)
    await session.commit()


async def render_public_data(
    session: AsyncSession, link: ShareLink
) -> dict[str, Any]:
    """Return a sanitized payload appropriate for an unauthenticated viewer."""
    data: dict[str, Any] = {
        "target_type": link.target_type,
        "view_count": link.view_count,
        "created_at": link.created_at.isoformat(),
    }
    if link.target_type == "content":
        c = (
            await session.execute(
                select(GeneratedContent).where(GeneratedContent.id == link.target_id)
            )
        ).scalar_one_or_none()
        if c is None or c.status != "complete":
            return {"target_type": "content", "missing": True}
        data["content_type"] = c.content_type
        data["style"] = c.style
        data["content_json"] = c.content_json
        data["has_file"] = bool(c.file_path)
    elif link.target_type == "media_job":
        m = (
            await session.execute(
                select(MediaJob).where(MediaJob.id == link.target_id)
            )
        ).scalar_one_or_none()
        if m is None or m.status != "complete":
            return {"target_type": "media_job", "missing": True}
        data["job_type"] = m.job_type
        data["duration_seconds"] = (
            float(m.duration_seconds) if m.duration_seconds else None
        )
        data["has_file"] = bool(m.output_path)
    elif link.target_type == "brief":
        b = (
            await session.execute(
                select(ResearchBrief).where(ResearchBrief.id == link.target_id)
            )
        ).scalar_one_or_none()
        if b is None or b.status != "complete":
            return {"target_type": "brief", "missing": True}
        data["topic"] = b.topic
        # Strip any user_id-like fields from the brief JSON for safety
        data["brief_json"] = _strip_pii(b.brief_json or {})
    return data


def _strip_pii(d: Any) -> Any:
    """Recursively drop user_id-shaped keys from a JSON-ish structure."""
    if isinstance(d, dict):
        return {
            k: _strip_pii(v)
            for k, v in d.items()
            if k not in ("user_id", "uploaded_by", "owner_id", "session_id", "ip", "email")
        }
    if isinstance(d, list):
        return [_strip_pii(x) for x in d]
    return d


async def resolve_target_file(
    session: AsyncSession, link: ShareLink
) -> Optional[Path]:
    """Return the on-disk path for the shared asset, or None."""
    if link.target_type == "content":
        c = (
            await session.execute(
                select(GeneratedContent).where(GeneratedContent.id == link.target_id)
            )
        ).scalar_one_or_none()
        if c and c.file_path and Path(c.file_path).exists():
            return Path(c.file_path)
    elif link.target_type == "media_job":
        m = (
            await session.execute(
                select(MediaJob).where(MediaJob.id == link.target_id)
            )
        ).scalar_one_or_none()
        if m and m.output_path and Path(m.output_path).exists():
            return Path(m.output_path)
    return None


# ─── OG thumbnail ───────────────────────────────────────────────────────────


def render_og_thumbnail(link: ShareLink, target_data: dict[str, Any]) -> bytes:
    """Render a 1200x630 PNG thumbnail server-side via Pillow.

    Returns the PNG bytes; the caller decides whether to cache them.
    """
    from PIL import Image, ImageDraw

    w, h = 1200, 630
    img = Image.new("RGB", (w, h), (16, 16, 28))
    draw = ImageDraw.Draw(img)

    title = "Shared from NexusMind"
    subtitle = ""
    if link.target_type == "content":
        title = (target_data.get("content_type") or "Content").replace("_", " ").title()
        subtitle = (target_data.get("style") or "").title()
    elif link.target_type == "media_job":
        title = (target_data.get("job_type") or "Media").replace("_", " ").title()
        subtitle = (
            f"{target_data.get('duration_seconds', 0):.1f}s"
            if target_data.get("duration_seconds")
            else ""
        )
    elif link.target_type == "brief":
        title = target_data.get("topic") or "Research Brief"
        subtitle = "Research Brief"

    # Brand banner
    draw.rectangle([0, 0, w, 12], fill=(80, 100, 220))
    draw.rectangle([0, h - 12, w, h], fill=(80, 100, 220))

    # Title
    title_font = _load_font(64)
    sub_font = _load_font(28)
    foot_font = _load_font(22)

    title_lines = _wrap(title, max_chars=24, max_lines=3)
    y = 140
    for line in title_lines:
        draw.text((80, y), line, fill=(255, 255, 255), font=title_font)
        y += 80

    if subtitle:
        draw.text((80, y + 20), subtitle, fill=(180, 180, 200), font=sub_font)
    draw.text((80, h - 70), "nexusmind", fill=(140, 160, 220), font=foot_font)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _load_font(size: int):
    from PIL import ImageFont

    for name in (
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        try:
            return ImageFont.truetype(name, size)
        except (OSError, ValueError):
            continue
    return ImageFont.load_default()


def _wrap(text: str, max_chars: int, max_lines: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        candidate = (cur + " " + w).strip()
        if len(candidate) <= max_chars:
            cur = candidate
        else:
            lines.append(cur)
            cur = w
        if len(lines) >= max_lines:
            break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    return lines or [text[:max_chars]]


# ─── Bundle export ──────────────────────────────────────────────────────────


def bundle_export(
    *,
    target_type: str,
    target_id: uuid.UUID,
    files: list[tuple[str, Path]],
    extra_text: dict[str, str] | None = None,
) -> Path:
    """Zip up all files for a target into a single bundle.

    `files` is [(name_in_zip, path_on_disk), ...].
    `extra_text` is {name_in_zip: utf8_text} for caption variants, transcripts, etc.
    """
    out_path = bundles_dir() / f"{target_type}_{target_id}.zip"
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, path in files:
            if path.exists():
                zf.write(path, arcname=name)
        for name, text in (extra_text or {}).items():
            zf.writestr(name, text.encode("utf-8"))
    return out_path
