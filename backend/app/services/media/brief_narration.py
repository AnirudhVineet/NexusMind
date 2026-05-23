"""Phase 5 Track B — Convert a research brief into a chaptered narration.

Splits the brief JSON into chapter-sized chunks (executive_summary, each
argument, each counterargument, gaps, reading list). Synthesizes audio for
each chapter and concatenates with FFmpeg into a single MP3 with chapter
metadata.
"""
from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.core.logging import get_logger
from app.services.media import audio_dir, scratch_dir
from app.services.media.ffmpeg_runner import run_ffmpeg
from app.services.media.tts import synthesize as tts_synthesize

log = get_logger(__name__)


@dataclass
class Chapter:
    heading: str
    text: str
    offset_seconds: float = 0.0
    duration_seconds: float = 0.0


def split_brief_into_chapters(brief_json: dict[str, Any]) -> list[Chapter]:
    """Return a list of Chapter objects ready for narration."""
    chapters: list[Chapter] = []
    topic = brief_json.get("topic") or "Research Brief"
    summary = brief_json.get("executive_summary")
    if summary:
        chapters.append(Chapter(heading=f"Executive Summary — {topic}", text=str(summary)))
    for i, arg in enumerate(brief_json.get("key_arguments") or [], start=1):
        if isinstance(arg, dict):
            claim = arg.get("claim") or ""
            stance = arg.get("stance") or "neutral"
            chapters.append(Chapter(heading=f"Argument {i} ({stance})", text=claim))
        else:
            chapters.append(Chapter(heading=f"Argument {i}", text=str(arg)))
    for i, ca in enumerate(brief_json.get("counterarguments") or [], start=1):
        if isinstance(ca, dict):
            text = ca.get("claim") or ca.get("text") or ""
        else:
            text = str(ca)
        if text:
            chapters.append(Chapter(heading=f"Counterargument {i}", text=text))
    gaps = brief_json.get("knowledge_gaps")
    if gaps:
        if isinstance(gaps, list):
            chapters.append(
                Chapter(heading="Knowledge Gaps", text="; ".join(str(g) for g in gaps))
            )
        else:
            chapters.append(Chapter(heading="Knowledge Gaps", text=str(gaps)))
    reading = brief_json.get("recommended_reading")
    if reading and isinstance(reading, list) and reading:
        items = []
        for r in reading[:5]:
            if isinstance(r, dict):
                items.append(r.get("title") or r.get("text") or "")
            else:
                items.append(str(r))
        items = [s for s in items if s]
        if items:
            chapters.append(
                Chapter(heading="Recommended Reading", text=". ".join(items))
            )
    return [c for c in chapters if c.text and c.text.strip()]


async def narrate_brief(
    brief_id: str,
    user_id: str,
    voice_id: str | None,
    speed: float,
) -> dict[str, Any]:
    """Produce a single MP3 from the brief with chapter offsets.

    Returns a dict with file_path, total_duration_seconds, chapters[].
    """
    from app.db.session import AsyncSessionLocal
    from app.models.research_brief import ResearchBrief

    async with AsyncSessionLocal() as session:
        brief = (
            await session.execute(
                select(ResearchBrief).where(ResearchBrief.id == brief_id)
            )
        ).scalar_one_or_none()
        if brief is None or not brief.brief_json:
            raise ValueError("Brief not found or empty")
        bjson = brief.brief_json if isinstance(brief.brief_json, dict) else {}

    chapters = split_brief_into_chapters(bjson)
    if not chapters:
        raise ValueError("Brief has no narratable content")

    work = scratch_dir() / f"brief_{brief_id}"
    work.mkdir(parents=True, exist_ok=True)
    per_clip: list[Path] = []
    offset = 0.0
    for i, ch in enumerate(chapters):
        # Prepend the heading as a brief pause + heading line
        spoken = f"{ch.heading}. {ch.text}"
        out = work / f"chap_{i:02d}.wav"
        result = await tts_synthesize(
            spoken, voice_id=voice_id, speed=speed, out_path=out
        )
        if result is None:
            log.warning("brief_narration.tts_fail", brief_id=brief_id, chapter=i)
            continue
        ch.offset_seconds = offset
        ch.duration_seconds = result.duration_seconds
        offset += result.duration_seconds
        per_clip.append(result.path)

    if not per_clip:
        raise RuntimeError("All TTS failed for brief narration")

    # Concat into a single MP3
    final_dir = audio_dir() / "briefs"
    final_dir.mkdir(parents=True, exist_ok=True)
    final_path = final_dir / f"{brief_id}.mp3"

    concat_list = work / "concat.txt"
    concat_list.write_text(
        "\n".join(f"file '{p.as_posix()}'" for p in per_clip), encoding="utf-8"
    )
    rc = await run_ffmpeg(
        [
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list),
            "-c:a",
            "libmp3lame",
            "-b:a",
            "128k",
            str(final_path),
        ]
    )
    # Best-effort scratch cleanup
    try:
        shutil.rmtree(work, ignore_errors=True)
    except Exception:  # pragma: no cover
        pass
    if rc != 0 or not final_path.exists():
        raise RuntimeError(f"FFmpeg concat exit code {rc}")

    return {
        "file_path": str(final_path),
        "total_duration_seconds": offset,
        "chapters": [
            {
                "heading": c.heading,
                "text": c.text,
                "offset_seconds": c.offset_seconds,
                "duration_seconds": c.duration_seconds,
            }
            for c in chapters
            if c.duration_seconds > 0
        ],
    }


async def run_brief_narration_job(media_job_id: str) -> None:
    """Celery entry point — wrap ``narrate_brief`` in a MediaJob lifecycle.

    Stages: queued → preparing → rendering → complete | failed.
    On any failure the narration quota increment is refunded.
    """
    from app.db.session import AsyncSessionLocal
    from app.models.media_job import MediaJob
    from app.models.voice import BriefNarration
    from app.services.media.quota_check import decrement_on_failure

    job_uuid = uuid.UUID(media_job_id)

    async with AsyncSessionLocal() as session:
        job = (
            await session.execute(
                select(MediaJob).where(MediaJob.id == job_uuid)
            )
        ).scalar_one_or_none()
        if job is None:
            log.error("brief_narration.job_missing", media_job_id=media_job_id)
            return
        params = job.params or {}
        brief_id = params.get("brief_id")
        voice_id = params.get("voice_id")
        speed = float(params.get("speed", 1.0))
        user_id = str(job.user_id)
        if not brief_id:
            job.status = "failed"
            job.stage = "failed"
            job.error_message = "Missing brief_id in job params"
            job.completed_at = datetime.now(timezone.utc)
            await session.commit()
            decrement_on_failure(user_id, "narration")
            return
        job.status = "rendering"
        job.stage = "synthesizing"
        job.progress_pct = 10
        job.started_at = datetime.now(timezone.utc)
        await session.commit()

    try:
        result = await narrate_brief(brief_id, user_id, voice_id, speed)
    except Exception as exc:
        log.exception("brief_narration.failed", media_job_id=media_job_id)
        async with AsyncSessionLocal() as session:
            job = (
                await session.execute(
                    select(MediaJob).where(MediaJob.id == job_uuid)
                )
            ).scalar_one_or_none()
            if job is not None:
                job.status = "failed"
                job.stage = "failed"
                job.error_message = str(exc)[:2000]
                job.completed_at = datetime.now(timezone.utc)
                await session.commit()
        decrement_on_failure(user_id, "narration")
        return

    # Success — persist the BriefNarration row + finalize the job.
    out_path = Path(result["file_path"])
    size_bytes = out_path.stat().st_size if out_path.exists() else None
    async with AsyncSessionLocal() as session:
        job = (
            await session.execute(
                select(MediaJob).where(MediaJob.id == job_uuid)
            )
        ).scalar_one_or_none()
        if job is None:
            return
        narration = BriefNarration(
            user_id=uuid.UUID(user_id),
            brief_id=uuid.UUID(brief_id),
            media_job_id=job.id,
            voice_id=voice_id,
            speed=Decimal(f"{speed:.2f}"),
            chapters=result["chapters"],
        )
        session.add(narration)
        job.status = "complete"
        job.stage = "complete"
        job.progress_pct = 100
        job.output_path = str(out_path)
        job.output_size_bytes = size_bytes
        job.duration_seconds = Decimal(
            f"{float(result['total_duration_seconds']):.3f}"
        )
        job.completed_at = datetime.now(timezone.utc)
        await session.commit()
