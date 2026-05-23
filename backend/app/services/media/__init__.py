"""Phase 5 — Media production services (reels, TTS, visual providers, storyboards)."""
from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings


def media_root() -> Path:
    """Resolve the absolute root directory for all generated media artifacts."""
    settings = get_settings()
    root = Path(settings.resolved_media_data_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def reels_dir() -> Path:
    p = media_root() / "reels"
    p.mkdir(parents=True, exist_ok=True)
    return p


def audio_dir() -> Path:
    p = media_root() / "audio"
    p.mkdir(parents=True, exist_ok=True)
    return p


def storyboards_dir() -> Path:
    p = media_root() / "storyboards"
    p.mkdir(parents=True, exist_ok=True)
    return p


def memes_dir() -> Path:
    p = media_root() / "memes"
    p.mkdir(parents=True, exist_ok=True)
    return p


def scratch_dir() -> Path:
    p = media_root() / "scratch"
    p.mkdir(parents=True, exist_ok=True)
    return p


def brandkit_dir() -> Path:
    p = media_root() / "brandkit"
    p.mkdir(parents=True, exist_ok=True)
    return p


def bundles_dir() -> Path:
    p = media_root() / "bundles"
    p.mkdir(parents=True, exist_ok=True)
    return p
