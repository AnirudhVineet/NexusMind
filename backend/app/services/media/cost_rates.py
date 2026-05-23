"""Phase 5 Track H — Per-provider cost rate cards.

All values are USD. Free providers report 0.0. Rates are rough order-of-
magnitude estimates and should not be used for billing — just budget
estimation. Update them as provider pricing shifts.
"""
from __future__ import annotations


# USD per 1M input units (characters for TTS, images for visuals, tokens for LLM)
_RATES_PER_M: dict[str, float] = {
    # TTS
    "piper": 0.0,
    "pyttsx3": 0.0,
    "elevenlabs": 30.0,        # turbo tier, per 1M chars
    "openai_tts": 15.0,        # tts-1
    # Visuals
    "pollinations": 0.0,
    "huggingface_sd": 0.0,     # free inference tier
    "pexels": 0.0,
    "solid_fallback": 0.0,
    "dalle3": 40_000.0,        # ~$0.04 per 1024x1024 → ~$40 per 1000 images
    "stability_api": 18_000.0, # per 1M imagined as per-thousand × 1000
    # LLM (already covered elsewhere; included for completeness)
    "groq": 0.0,
    "ollama": 0.0,
    "openai_gpt": 5.0,
}


def estimate_cost(provider: str, units: int, kind: str = "char") -> float:
    """Return an estimated cost in USD for the given (provider, units, kind).

    `kind`: "char" / "image" / "token". For images, 1 unit == 1 image (rate
    is "per 1M images"); for chars/tokens, 1 unit == 1 char or token.
    """
    if units <= 0:
        return 0.0
    rate = _RATES_PER_M.get(provider, 0.0)
    return (units / 1_000_000.0) * rate


def rate_card() -> dict[str, float]:
    """Return a copy of the full rate table for diagnostics."""
    return dict(_RATES_PER_M)
