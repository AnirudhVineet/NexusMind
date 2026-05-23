"""Phase 5 Track A — FFmpeg subprocess wrapper with progress parsing.

Detection order:
  1. settings.ffmpeg_path (env override)
  2. imageio_ffmpeg.get_ffmpeg_exe() (vendored binary)
  3. shutil.which("ffmpeg") (system PATH)

If none works the worker logs a fatal startup error with install instructions
and refuses to accept reel jobs.
"""
from __future__ import annotations

import asyncio
import re
import shutil
import subprocess
from pathlib import Path
from typing import Awaitable, Callable, Optional

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)

_FFMPEG_PATH: Optional[str] = None
_DETECTION_DONE = False

_PROGRESS_RE = re.compile(r"out_time_ms=(\d+)")
_HARD_KILL_SECONDS = 8 * 60


class FFmpegMissingError(RuntimeError):
    """Raised when no FFmpeg binary can be located."""


def detect_ffmpeg() -> Optional[str]:
    """Return path to an ffmpeg binary, or None.

    Caches the result for the lifetime of the process.
    """
    global _FFMPEG_PATH, _DETECTION_DONE
    if _DETECTION_DONE:
        return _FFMPEG_PATH

    settings = get_settings()
    candidates: list[str] = []

    if settings.ffmpeg_path:
        candidates.append(settings.ffmpeg_path)

    try:
        import imageio_ffmpeg  # type: ignore

        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe:
            candidates.append(exe)
    except Exception:  # pragma: no cover — import guard
        pass

    sys_path = shutil.which("ffmpeg")
    if sys_path:
        candidates.append(sys_path)

    for c in candidates:
        if c and Path(c).exists():
            _FFMPEG_PATH = c
            log.info("ffmpeg.detected", path=c)
            break
    else:
        log.error(
            "ffmpeg.missing",
            hint=(
                "Install via: winget install Gyan.FFmpeg "
                "OR pip install imageio-ffmpeg"
            ),
        )

    _DETECTION_DONE = True
    return _FFMPEG_PATH


def require_ffmpeg() -> str:
    path = detect_ffmpeg()
    if not path:
        raise FFmpegMissingError(
            "FFmpeg not found. Install with `winget install Gyan.FFmpeg` "
            "or `pip install imageio-ffmpeg`."
        )
    return path


async def run_ffmpeg(
    args: list[str],
    *,
    on_progress: Optional[Callable[[float], Awaitable[None] | None]] = None,
    duration_seconds: Optional[float] = None,
) -> int:
    """Run ffmpeg with a list of args (no `ffmpeg` prefix).

    If on_progress is provided and duration_seconds is known, parses the
    `out_time_ms=` lines emitted by `-progress pipe:1` and calls on_progress
    with a float in [0.0, 1.0].

    Returns the process exit code. Hard-kills the process after 8 minutes.
    """
    ffmpeg = require_ffmpeg()

    if on_progress is not None:
        # Insert `-progress pipe:1` so we can parse line-by-line progress
        if "-progress" not in args:
            args = ["-progress", "pipe:1", "-nostats", *args]

    cmd = [ffmpeg, "-y", *args]
    log.info("ffmpeg.run", cmd=" ".join(cmd[:6]))

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    async def _kill_after_timeout() -> None:
        await asyncio.sleep(_HARD_KILL_SECONDS)
        if proc.returncode is None:
            log.error("ffmpeg.hard_kill", pid=proc.pid)
            try:
                proc.kill()
            except ProcessLookupError:
                pass

    killer = asyncio.create_task(_kill_after_timeout())

    async def _read_progress(stream: asyncio.StreamReader) -> None:
        if not on_progress or not duration_seconds or duration_seconds <= 0:
            # Drain anyway
            while True:
                line = await stream.readline()
                if not line:
                    break
            return
        while True:
            line = await stream.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace")
            m = _PROGRESS_RE.search(text)
            if m:
                ms = int(m.group(1))
                pct = max(0.0, min(1.0, (ms / 1_000_000.0) / duration_seconds))
                result = on_progress(pct)
                if asyncio.iscoroutine(result):
                    await result

    async def _drain_err(stream: asyncio.StreamReader) -> bytes:
        buf = bytearray()
        while True:
            line = await stream.readline()
            if not line:
                break
            buf.extend(line)
        return bytes(buf)

    stdout_task = asyncio.create_task(_read_progress(proc.stdout))  # type: ignore[arg-type]
    stderr_task = asyncio.create_task(_drain_err(proc.stderr))  # type: ignore[arg-type]

    try:
        rc = await proc.wait()
    finally:
        killer.cancel()
        await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)

    if rc != 0:
        err = stderr_task.result()
        if isinstance(err, (bytes, bytearray)):
            log.error(
                "ffmpeg.failed",
                rc=rc,
                stderr_tail=err[-2000:].decode("utf-8", errors="replace"),
            )
    return rc


def ffprobe_duration(path: str | Path) -> float:
    """Synchronously probe a media file's duration in seconds via ffprobe.

    Falls back to ffmpeg -i parsing if ffprobe isn't on PATH.
    Returns 0.0 on failure.
    """
    ffmpeg = detect_ffmpeg()
    if not ffmpeg:
        return 0.0
    probe = shutil.which("ffprobe")
    if probe:
        try:
            out = subprocess.run(
                [
                    probe,
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if out.returncode == 0:
                return float(out.stdout.strip() or 0.0)
        except Exception:  # pragma: no cover
            return 0.0
    # Fallback: parse ffmpeg -i output (ugly but works)
    try:
        proc = subprocess.run(
            [ffmpeg, "-i", str(path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        m = re.search(r"Duration:\s+(\d+):(\d+):(\d+\.\d+)", proc.stderr)
        if m:
            h, mn, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
            return h * 3600 + mn * 60 + s
    except Exception:  # pragma: no cover
        return 0.0
    return 0.0
