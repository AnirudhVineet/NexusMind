"""Track H — /metrics endpoint exposes Phase 5 series after a sample
metric is recorded."""
from __future__ import annotations

from prometheus_client import generate_latest

from app.core import metrics as M


def test_media_metrics_appear_in_export_after_recording():
    M.MEDIA_JOBS_TOTAL.labels(job_type="reel", status="complete").inc()
    M.MEDIA_COST_USD_TOTAL.labels(provider="piper").inc(0)
    payload = generate_latest().decode("utf-8")
    assert "nexusmind_media_jobs_total" in payload
    assert "nexusmind_media_cost_usd_total" in payload


def test_quota_status_endpoint_shape():
    # Pure unit-level shape check on the quota module — no DB hit needed
    from app.services.media.quota_check import current_usage

    cur, cap = current_usage("user-123", "reel")
    assert cur >= 0
    assert cap > 0
