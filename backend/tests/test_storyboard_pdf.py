"""Track D — PDF storyboard renderer (sync portion only)."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.media import storyboard_renderer
from app.services.media.storyboard_renderer import Frame, coerce_frames


def test_coerce_frames_normalizes_input():
    payload = {
        "frames": [
            {"index": 1, "narration": "n1", "visual": "v1", "duration_seconds": 5},
            {"narration": "n2"},  # missing index defaults to enumerate
            {"not_a_frame": True},
        ]
    }
    frames = coerce_frames(payload)
    assert len(frames) == 3
    assert frames[0].index == 1
    assert frames[1].index == 2  # auto-assigned
    assert frames[1].narration == "n2"
    assert frames[1].duration == 5.0  # default


def test_enforce_frame_cap_rejects_over_cap(monkeypatch):
    big = [Frame(index=i, narration="", visual="", audio_note="", duration=1.0) for i in range(50)]
    with pytest.raises(ValueError):
        storyboard_renderer._enforce_frame_cap(big)


def test_render_pdf_writes_file(tmp_path):
    """Run only the synchronous PDF render with a placeholder image."""
    from PIL import Image

    img_path = tmp_path / "vis.png"
    Image.new("RGB", (200, 100), (40, 40, 80)).save(img_path)
    frames = [
        Frame(index=1, narration="First frame.", visual="A scene", audio_note="", duration=4.0),
        Frame(index=2, narration="Second frame.", visual="Another scene", audio_note="", duration=5.0),
    ]
    visuals = [(img_path, "test"), (img_path, "test")]
    audio_paths = [None, None]

    out = tmp_path / "out.pdf"
    storyboard_renderer._render_pdf(out, frames, visuals, audio_paths)
    assert out.exists()
    assert out.stat().st_size > 100
    # Confirm it's a PDF — the magic number is "%PDF-"
    assert out.read_bytes()[:5] == b"%PDF-"
