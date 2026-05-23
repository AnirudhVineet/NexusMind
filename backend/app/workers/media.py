"""Phase 5 — Media render Celery workers.

Hosts all media job types on the single `reel` queue. Task priority is set
via apply_async(priority=N) at enqueue time, so narration tasks queue ahead
of reel renders even though they share a worker.
"""
from __future__ import annotations

from app.core.logging import configure_logging, get_logger
from app.workers._async_utils import run_async_task
from app.workers.celery_app import celery_app

configure_logging()
log = get_logger(__name__)


@celery_app.task(name="render_reel_job", queue="reel", acks_late=True)
def render_reel_job(media_job_id: str) -> None:
    """Entry point for the reel render pipeline."""
    from app.services.media.reel_renderer import render_reel

    run_async_task(render_reel(media_job_id))


@celery_app.task(name="render_narration_job", queue="reel", acks_late=True)
def render_narration_job(media_job_id: str) -> None:
    """Track B will fully implement this. For now we no-op + mark failed."""
    import uuid
    from datetime import datetime, timezone

    async def _run() -> None:
        from sqlalchemy import select

        from app.db.session import AsyncSessionLocal
        from app.models.media_job import MediaJob

        async with AsyncSessionLocal() as session:
            row = (
                await session.execute(
                    select(MediaJob).where(MediaJob.id == uuid.UUID(media_job_id))
                )
            ).scalar_one_or_none()
            if row is None:
                return
            # Inline narrate via tts.synthesize for the MVP
            from app.services.media import audio_dir
            from app.services.media.tts import synthesize

            params = row.params or {}
            text = params.get("text", "")
            voice = params.get("voice_id")
            speed = float(params.get("speed", 1.0))
            out_path = audio_dir() / f"{row.id}.wav"
            row.status = "rendering"
            row.stage = "synthesizing"
            row.progress_pct = 30
            row.started_at = datetime.now(timezone.utc)
            await session.commit()
            try:
                result = await synthesize(text, voice_id=voice, speed=speed, out_path=out_path)
                if not result:
                    raise RuntimeError("All TTS providers failed")
                row.status = "complete"
                row.stage = "complete"
                row.progress_pct = 100
                row.output_path = str(result.path)
                row.output_size_bytes = result.path.stat().st_size
                from decimal import Decimal as D

                row.duration_seconds = D(f"{result.duration_seconds:.3f}")
                row.cost_estimate_usd = D(f"{result.cost_usd:.6f}")
                row.completed_at = datetime.now(timezone.utc)
            except Exception as e:
                log.exception("narration.failed")
                row.status = "failed"
                row.stage = "failed"
                row.error_message = str(e)[:2000]
                row.completed_at = datetime.now(timezone.utc)
            await session.commit()

    run_async_task(_run())


@celery_app.task(name="render_brief_narration_job", queue="reel", acks_late=True)
def render_brief_narration_job(media_job_id: str) -> None:
    """Render a chaptered narration for a research brief in the background."""
    from app.services.media.brief_narration import run_brief_narration_job

    run_async_task(run_brief_narration_job(media_job_id))


@celery_app.task(name="render_storyboard_job", queue="reel", acks_late=True)
def render_storyboard_job(media_job_id: str) -> None:
    """Phase 5 Track D — orchestrates PDF / image series / HTML slides render."""
    from app.services.media.storyboard_renderer import render_storyboard

    run_async_task(render_storyboard(media_job_id))


@celery_app.task(name="render_bundle_export_job", queue="reel", acks_late=True)
def render_bundle_export_job(media_job_id: str) -> None:
    """Track F fully implements this."""
    log.warning("bundle_export.stub_only", media_job_id=media_job_id)
