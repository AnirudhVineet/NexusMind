"""Track A — reel pipeline beat coercion + duration validation."""
from __future__ import annotations

import pytest

from app.services.media import reel_renderer


def test_coerce_beats_full_payload():
    payload = {
        "hook": {"text": "Did you know?", "duration_seconds": 4},
        "beats": [
            {"text": "Beat 1", "duration_seconds": 8, "on_screen_text": "Hello"},
            {"text": "Beat 2", "duration_seconds": 8},
        ],
        "cta": {"text": "Follow for more", "duration_seconds": 3},
    }
    beats = reel_renderer._coerce_beats(payload)
    assert [b.kind for b in beats] == ["hook", "beat", "beat", "cta"]
    assert beats[0].duration == 4
    assert beats[1].on_screen_text == "Hello"
    assert beats[-1].duration == 3


def test_coerce_beats_handles_missing_optional_fields():
    payload = {"beats": [{"text": "Only this"}]}
    beats = reel_renderer._coerce_beats(payload)
    assert len(beats) == 1
    assert beats[0].duration == 10  # default fill


def test_validate_duration_rejects_over_cap(monkeypatch):
    # Simulate a 5-minute reel
    payload = {"beats": [{"text": "x", "duration_seconds": 60}] * 6}
    beats = reel_renderer._coerce_beats(payload)
    with pytest.raises(ValueError):
        reel_renderer._validate_duration(beats)


def test_validate_duration_rejects_zero():
    with pytest.raises(ValueError):
        reel_renderer._validate_duration([])
