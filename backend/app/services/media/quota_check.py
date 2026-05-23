"""Phase 5 — Lightweight quota gate used by media API endpoints.

The full quota service with cost tracking lives in Track H. This module
provides synchronous pre-flight checks against per-job-type daily caps in
Redis. If Redis is unavailable the gate fails open with a warning (so dev
environments without Redis don't break).
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)


def _daily_key(user_id: str, job_type: str) -> str:
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"nm:quota:{user_id}:{day}:{job_type}"


def _cap_for(job_type: str) -> int:
    s = get_settings()
    return {
        "reel": s.reel_daily_cap,
        "narration": s.narration_daily_cap,
        "storyboard": s.storyboard_daily_cap,
        "meme_image": s.meme_daily_cap,
        "export": 50,
    }.get(job_type, 50)


def check_and_increment(user_id: str, job_type: str) -> tuple[bool, int, int]:
    """Atomic INCR + check. Returns (allowed, current_count, cap).

    On Redis failure returns (True, 0, cap) and logs a warning — we don't
    block media work when the cache is down.
    """
    cap = _cap_for(job_type)
    try:
        import redis  # type: ignore

        client = redis.Redis.from_url(get_settings().redis_url)
        key = _daily_key(user_id, job_type)
        current = client.incr(key)
        # 26h expiry so it definitely covers the day boundary
        client.expire(key, 60 * 60 * 26)
        if current > cap:
            return False, int(current), cap
        return True, int(current), cap
    except Exception as e:
        log.warning("quota.redis.unavailable", error=str(e)[:200])
        return True, 0, cap


def decrement_on_failure(user_id: str, job_type: str) -> None:
    """Roll back the increment when a job fails before any real work."""
    try:
        import redis  # type: ignore

        client = redis.Redis.from_url(get_settings().redis_url)
        key = _daily_key(user_id, job_type)
        client.decr(key)
    except Exception:
        pass


def current_usage(user_id: str, job_type: str) -> tuple[int, int]:
    """Return (current_count, cap) without incrementing."""
    cap = _cap_for(job_type)
    try:
        import redis  # type: ignore

        client = redis.Redis.from_url(get_settings().redis_url)
        raw = client.get(_daily_key(user_id, job_type))
        return int(raw or 0), cap
    except Exception:
        return 0, cap
