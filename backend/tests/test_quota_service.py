"""Track H — quota / cost service shape and helpers."""
from __future__ import annotations

import sys

import pytest

from app.services.media import cost_rates, quota


def test_cap_for_returns_positive_for_known_types():
    for t in ("reel", "narration", "storyboard", "meme_image"):
        assert quota.cap_for(t) > 0


def test_cap_for_unknown_type_returns_default():
    assert quota.cap_for("never-heard-of-it") > 0


def test_cost_rates_includes_known_providers():
    table = cost_rates.rate_card()
    for k in ("piper", "pyttsx3", "elevenlabs", "openai_tts", "pollinations"):
        assert k in table


def test_estimate_cost_zero_for_free_providers():
    assert cost_rates.estimate_cost("piper", 100_000, kind="char") == 0.0
    assert cost_rates.estimate_cost("pollinations", 5, kind="image") == 0.0


def test_estimate_cost_nonzero_for_paid_providers():
    # 1M chars on ElevenLabs ≈ $30
    cost = cost_rates.estimate_cost("elevenlabs", 1_000_000, kind="char")
    assert cost > 0
    # Linear scaling
    cost_half = cost_rates.estimate_cost("elevenlabs", 500_000, kind="char")
    assert abs(cost / 2 - cost_half) < 1e-6


def test_check_and_increment_re_exported_from_quota():
    # quota.py re-exports the Track A helpers
    from app.services.media.quota import (
        check_and_increment,
        current_usage,
        decrement_on_failure,
    )
    assert callable(check_and_increment)
    assert callable(current_usage)
    assert callable(decrement_on_failure)
