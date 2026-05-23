"""Phase 5 Track H — Periodic cleanup of expired media + scratch dirs."""
from __future__ import annotations

import asyncio
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.core.logging import configure_logging, get_logger
from app.services.media import scratch_dir
from app.workers.celery_app import celery_app

configure_logging()
log = get_logger(__name__)

SCRATCH_MAX_AGE_S = 6 * 60 * 60  # 6 hours


@celery_app.task(name="cleanup_expired_media", queue="maintenance")
def cleanup_expired_media() -> dict:
    """Delete media_jobs files + DB rows past expires_at."""
    asyncio.run(_cleanup_expired_media_impl())
    return {"ok": True}


async def _cleanup_expired_media_impl() -> None:
    from app.db.session import AsyncSessionLocal
    from app.models.media_job import MediaJob

    deleted = 0
    async with AsyncSessionLocal() as session:
        now = datetime.now(timezone.utc)
        rows = (
            await session.execute(
                select(MediaJob).where(
                    MediaJob.expires_at.is_not(None),
                    MediaJob.expires_at < now,
                )
            )
        ).scalars().all()
        for row in rows:
            if row.output_path:
                try:
                    Path(row.output_path).unlink(missing_ok=True)
                except Exception as e:
                    log.warning("cleanup.media.unlink_fail", error=str(e)[:200])
            await session.delete(row)
            deleted += 1
        if deleted:
            await session.commit()
            log.info("cleanup.media.deleted", count=deleted)


@celery_app.task(name="cleanup_orphan_scratch_dirs", queue="maintenance")
def cleanup_orphan_scratch_dirs() -> dict:
    """Drop any scratch subdirectories older than 6 hours."""
    base = scratch_dir()
    if not base.exists():
        return {"removed": 0}
    cutoff = time.time() - SCRATCH_MAX_AGE_S
    removed = 0
    for sub in base.iterdir():
        if not sub.is_dir():
            continue
        try:
            mtime = sub.stat().st_mtime
        except FileNotFoundError:
            continue
        if mtime < cutoff:
            try:
                shutil.rmtree(sub, ignore_errors=True)
                removed += 1
            except Exception as e:
                log.warning("cleanup.scratch.fail", path=str(sub), error=str(e)[:200])
    if removed:
        log.info("cleanup.scratch.removed", count=removed)
    return {"removed": removed}
