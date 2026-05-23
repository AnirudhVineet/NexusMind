"""Phase 5 Track H — Full quota + cost service.

Wraps the lightweight `quota_check` module from Track A with:
  • Disk quota: sum of media_jobs.output_size_bytes for non-expired rows
  • Per-job-type daily caps (same as Track A but exposed for the UI)
  • Per-user cost rollup over the last 24h / 7d / 30d windows
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.generation_metric import GenerationMetric
from app.models.media_job import MediaJob
from app.services.media.quota_check import (
    _cap_for,
    check_and_increment,
    current_usage,
    decrement_on_failure,
)

__all__ = [
    "check_and_increment",
    "current_usage",
    "decrement_on_failure",
    "compute_disk_usage",
    "compute_cost_rollup",
    "all_quota_status",
]


async def compute_disk_usage(session: AsyncSession, user_id: uuid.UUID) -> int:
    """Sum output_size_bytes across this user's non-expired media_jobs."""
    now = datetime.now(timezone.utc)
    stmt = select(func.coalesce(func.sum(MediaJob.output_size_bytes), 0)).where(
        MediaJob.user_id == user_id,
        MediaJob.output_size_bytes.is_not(None),
    ).where(
        (MediaJob.expires_at.is_(None)) | (MediaJob.expires_at > now)
    )
    total = (await session.execute(stmt)).scalar_one()
    return int(total or 0)


async def compute_cost_rollup(
    session: AsyncSession, user_id: uuid.UUID, window_days: int = 1
) -> dict[str, float]:
    """Return {'total_usd', 'by_provider': {provider: usd}} for the window."""
    since = datetime.now(timezone.utc) - timedelta(days=window_days)
    rows = (
        await session.execute(
            select(
                GenerationMetric.provider,
                func.coalesce(func.sum(GenerationMetric.cost_estimate_usd), 0),
            )
            .where(
                GenerationMetric.user_id == user_id,
                GenerationMetric.created_at >= since,
            )
            .group_by(GenerationMetric.provider)
        )
    ).all()
    by_provider = {(r[0] or "unknown"): float(r[1] or 0) for r in rows}
    return {
        "total_usd": sum(by_provider.values()),
        "by_provider": by_provider,
        "window_days": window_days,
    }


async def all_quota_status(
    session: AsyncSession, user_id: uuid.UUID
) -> dict[str, Any]:
    """Single endpoint payload for the Studio quota strip."""
    settings = get_settings()
    by_type: dict[str, dict[str, int]] = {}
    for job_type in ("reel", "narration", "storyboard", "meme_image"):
        cur, cap = current_usage(str(user_id), job_type)
        by_type[job_type] = {"current": cur, "cap": cap}

    disk_used = await compute_disk_usage(session, user_id)
    cost = await compute_cost_rollup(session, user_id, window_days=1)
    return {
        "by_type": by_type,
        "disk": {
            "used_bytes": disk_used,
            "cap_bytes": settings.media_user_quota_bytes,
        },
        "cost_today_usd": cost["total_usd"],
        "cost_by_provider_today": cost["by_provider"],
    }


def cap_for(job_type: str) -> int:
    return _cap_for(job_type)
