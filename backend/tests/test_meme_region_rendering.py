"""Track C — region-driven meme renderer."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.media import meme_renderer


@pytest.fixture
def fake_template_dir(tmp_path, monkeypatch):
    """Build a tiny synthetic template + sidecar pair under tmp_path."""
    monkeypatch.setattr(meme_renderer, "TEMPLATES_DIR", tmp_path)

    from PIL import Image

    img = Image.new("RGB", (400, 400), (50, 50, 60))
    img.save(tmp_path / "drake.png")

    monkeypatch.setattr(meme_renderer, "memes_dir", lambda: tmp_path / "out")
    (tmp_path / "out").mkdir(parents=True, exist_ok=True)
    return tmp_path


def test_render_known_template_writes_file(fake_template_dir):
    out = meme_renderer.render_meme(
        "drake", {"reject": "writing tests", "approve": "shipping bugs"}
    )
    assert out is not None
    assert out.exists()
    assert out.stat().st_size > 0


def test_render_missing_template_falls_back_to_drake(fake_template_dir):
    out = meme_renderer.render_meme(
        "nonexistent_template",
        {"reject": "a", "approve": "b"},
    )
    # Sidecar lookup for the unknown key returns None, so render should return None
    assert out is None


def test_legacy_top_bottom_keys_still_work(fake_template_dir):
    out = meme_renderer.render_meme("drake", {"top": "old", "bottom": "shape"})
    assert out is not None


def test_list_templates_returns_metadata():
    templates = meme_renderer.list_templates()
    assert len(templates) > 0
    keys = {t["key"] for t in templates}
    # Phase 4 originals + Phase 5 additions
    for expected in ("drake", "two_buttons", "galaxy_brain", "this_is_fine", "custom"):
        assert expected in keys
