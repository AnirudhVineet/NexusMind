"""Track B — TTS provider chain falls through correctly."""
from __future__ import annotations

import wave
from pathlib import Path

import pytest

from app.services.media import tts


def _write_silent_wav(path: Path, seconds: float = 1.0) -> None:
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(22050)
        wf.writeframes(b"\x00\x00" * int(22050 * seconds))


class _OkProvider:
    name = "ok-mock"

    async def available(self) -> bool:
        return True

    async def synthesize(self, text, voice_id, speed, out_path):
        _write_silent_wav(out_path)
        return tts.AudioResult(
            path=out_path,
            duration_seconds=1.0,
            sample_rate=22050,
            provider_used=self.name,
        )


class _UnavailableProvider:
    name = "unavail-mock"

    async def available(self) -> bool:
        return False

    async def synthesize(self, text, voice_id, speed, out_path):
        raise AssertionError("should never be called")


class _FailingProvider:
    name = "failing-mock"

    async def available(self) -> bool:
        return True

    async def synthesize(self, text, voice_id, speed, out_path):
        return None


@pytest.mark.asyncio
async def test_synthesize_picks_first_working_provider(tmp_path, monkeypatch):
    tts._PROVIDER_CACHE = [_UnavailableProvider(), _FailingProvider(), _OkProvider()]
    try:
        out = tmp_path / "out.wav"
        result = await tts.synthesize("Hello world", out_path=out)
    finally:
        tts._PROVIDER_CACHE = None
    assert result is not None
    assert result.provider_used == "ok-mock"
    assert result.path.exists()


@pytest.mark.asyncio
async def test_empty_text_returns_none(tmp_path):
    out = tmp_path / "out.wav"
    result = await tts.synthesize("   ", out_path=out)
    assert result is None


@pytest.mark.asyncio
async def test_cache_hit_skips_providers(tmp_path, monkeypatch):
    # Pre-populate the cache path with a valid WAV; synthesize should
    # short-circuit without invoking any provider.
    monkeypatch.setattr(tts, "audio_dir", lambda: tmp_path)
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    h = tts._hash("hello cache", None, 1.0)
    cache_file = cache_dir / f"{h}.wav"
    _write_silent_wav(cache_file)

    tts._PROVIDER_CACHE = [_FailingProvider()]
    try:
        result = await tts.synthesize("hello cache")
    finally:
        tts._PROVIDER_CACHE = None
    assert result is not None
    assert result.provider_used == "cache"
