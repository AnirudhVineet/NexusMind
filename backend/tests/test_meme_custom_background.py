"""Track C — custom AI-background memes."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.media import meme_renderer


@pytest.mark.asyncio
async def test_custom_meme_uses_visual_provider(tmp_path, monkeypatch):
    """Validate that render_custom_meme produces a PNG. The visual_provider
    falls back to SolidColorFallback when no other provider works."""
    monkeypatch.setattr(meme_renderer, "memes_dir", lambda: tmp_path)

    # Force only the solid fallback so the test is deterministic
    from app.services.media import visual_provider

    visual_provider._PROVIDER_CACHE = [visual_provider.SolidColorFallback()]
    monkeypatch.setattr(visual_provider, "media_root", lambda: tmp_path)
    try:
        out = await meme_renderer.render_custom_meme(
            main_text="A bold claim about AI",
            background_prompt="abstract neural network",
            out_path=tmp_path / "custom.png",
        )
    finally:
        visual_provider._PROVIDER_CACHE = None

    assert out is not None
    assert out.exists()
    assert out.stat().st_size > 0
