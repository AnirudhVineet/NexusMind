"""Track B — TTS provider availability detection (no Piper install required)."""
from __future__ import annotations

import pytest

from app.services.media import tts


@pytest.mark.asyncio
async def test_piper_provider_unavailable_without_models(monkeypatch):
    provider = tts.PiperProvider()

    def _no_exe():
        return None

    monkeypatch.setattr(provider, "_piper_exe", _no_exe)
    available = await provider.available()
    assert available is False


@pytest.mark.asyncio
async def test_voice_catalog_returns_entries():
    voices = await tts.list_voices()
    assert isinstance(voices, list)
    assert len(voices) >= 1
    for v in voices:
        assert "voice_id" in v
        assert "provider" in v
        assert "label" in v


@pytest.mark.asyncio
async def test_pyttsx3_provider_signals_availability():
    """Pyttsx3 might or might not be installed — test that available()
    doesn't raise and returns a bool either way."""
    provider = tts.Pyttsx3Provider()
    result = await provider.available()
    assert isinstance(result, bool)


def test_synth_cache_key_is_deterministic():
    h1 = tts._hash("hello", "voice-a", 1.0)
    h2 = tts._hash("hello", "voice-a", 1.0)
    h3 = tts._hash("hello", "voice-b", 1.0)
    assert h1 == h2
    assert h1 != h3
