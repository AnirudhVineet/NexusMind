"""Track G — confirm the brand kit propagates into reel-render decisions."""
from __future__ import annotations

import inspect

from app.services.media import reel_renderer


def test_reel_concat_signature_accepts_brand_kit():
    sig = inspect.signature(reel_renderer._concat_and_finalize)
    assert "brand_kit" in sig.parameters


def test_reel_renderer_imports_brandkit_service():
    src = inspect.getsource(reel_renderer)
    assert "from app.services.brandkit import load_brandkit" in src
