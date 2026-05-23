"""Track A — FFmpeg runner detection + error paths."""
from __future__ import annotations

import pytest

from app.services.media import ffmpeg_runner


def test_detect_ffmpeg_returns_path_or_none(monkeypatch):
    # Reset cache so detection re-runs
    ffmpeg_runner._FFMPEG_PATH = None
    ffmpeg_runner._DETECTION_DONE = False
    result = ffmpeg_runner.detect_ffmpeg()
    # Result depends on the environment; either a string path or None
    assert result is None or isinstance(result, str)


def test_require_ffmpeg_raises_when_missing(monkeypatch):
    ffmpeg_runner._FFMPEG_PATH = None
    ffmpeg_runner._DETECTION_DONE = False

    def _no_detect():
        ffmpeg_runner._DETECTION_DONE = True
        return None

    monkeypatch.setattr(ffmpeg_runner, "detect_ffmpeg", _no_detect)
    with pytest.raises(ffmpeg_runner.FFmpegMissingError):
        ffmpeg_runner.require_ffmpeg()


def test_progress_regex_matches_pattern():
    sample = "frame=10\nfps=30\nout_time_ms=2500000\nbitrate=1024kbps\n"
    m = ffmpeg_runner._PROGRESS_RE.search(sample)
    assert m is not None
    assert int(m.group(1)) == 2_500_000


def test_ffprobe_duration_safe_on_missing():
    # Non-existent file should return 0.0 instead of raising
    out = ffmpeg_runner.ffprobe_duration("/tmp/does-not-exist-xyz.mp4")
    assert out == 0.0
