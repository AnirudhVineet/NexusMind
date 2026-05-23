"""Track A — visual provider chain falls through correctly."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.media import visual_provider


@pytest.mark.asyncio
async def test_solid_fallback_always_produces_image(tmp_path, monkeypatch):
    monkeypatch.setattr(visual_provider, "media_root", lambda: tmp_path)
    # Drop the first three providers so only SolidColorFallback runs
    visual_provider._PROVIDER_CACHE = [visual_provider.SolidColorFallback()]
    try:
        path, prov = await visual_provider.generate_visual(
            "futuristic city skyline at sunset", "square"
        )
    finally:
        visual_provider._PROVIDER_CACHE = None
    assert prov == "solid_fallback"
    assert path.exists()
    assert path.stat().st_size > 0


@pytest.mark.asyncio
async def test_provider_chain_skips_failing_ones(tmp_path, monkeypatch):
    monkeypatch.setattr(visual_provider, "media_root", lambda: tmp_path)

    class FailingProvider:
        name = "always_fails"

        async def generate(self, prompt, aspect, seed=0):
            return None

    visual_provider._PROVIDER_CACHE = [
        FailingProvider(),
        FailingProvider(),
        visual_provider.SolidColorFallback(),
    ]
    try:
        path, prov = await visual_provider.generate_visual("test prompt", "vertical")
    finally:
        visual_provider._PROVIDER_CACHE = None

    assert prov == "solid_fallback"
    assert path.exists()


@pytest.mark.asyncio
async def test_parallel_generation_runs_all_prompts(tmp_path, monkeypatch):
    monkeypatch.setattr(visual_provider, "media_root", lambda: tmp_path)
    visual_provider._PROVIDER_CACHE = [visual_provider.SolidColorFallback()]
    try:
        out = await visual_provider.generate_visuals_parallel(
            ["a", "b", "c"], "vertical", max_concurrent=2
        )
    finally:
        visual_provider._PROVIDER_CACHE = None
    assert len(out) == 3
    for path, _prov in out:
        assert path.exists()
