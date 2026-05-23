"""Track F — OG thumbnail rendering."""
from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.publish import render_og_thumbnail


def _link(target_type: str):
    # SimpleNamespace stand-in: avoids loading the full SQLAlchemy mapper
    # registry (the renderer only reads target_type).
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        target_type=target_type,
        target_id=uuid.uuid4(),
        slug="abcDEF123456",
        password_hash=None,
        expires_at=None,
        view_count=0,
        enabled=True,
        created_at=datetime.now(timezone.utc),
    )


def test_render_og_returns_png_bytes():
    link = _link("brief")
    data = {"topic": "Quantum Computing", "view_count": 7}
    png = render_og_thumbnail(link, data)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 1000  # actually rendered something


def test_render_og_handles_each_target_type():
    for target in ("content", "media_job", "brief"):
        link = _link(target)
        png = render_og_thumbnail(link, {})
        assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_og_dimensions():
    from PIL import Image

    link = _link("brief")
    png = render_og_thumbnail(link, {"topic": "Hi"})
    img = Image.open(io.BytesIO(png))
    assert img.size == (1200, 630)
