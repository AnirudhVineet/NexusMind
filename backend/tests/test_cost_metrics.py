"""Track H — Prometheus media metrics are registered with expected labels."""
from __future__ import annotations

from app.core import metrics as M


def test_media_metric_names_present():
    # Each metric must be defined at module level and registered
    assert hasattr(M, "MEDIA_JOBS_TOTAL")
    assert hasattr(M, "MEDIA_JOB_DURATION")
    assert hasattr(M, "MEDIA_COST_USD_TOTAL")
    assert hasattr(M, "VISUAL_PROVIDER_CALLS")
    assert hasattr(M, "TTS_PROVIDER_CALLS")
    assert hasattr(M, "MEDIA_DISK_USED_BYTES")


def test_media_jobs_counter_labels():
    # Accessing .labels() with the correct names should not raise
    M.MEDIA_JOBS_TOTAL.labels(job_type="reel", status="complete").inc()


def test_visual_provider_counter_labels():
    M.VISUAL_PROVIDER_CALLS.labels(provider="pollinations", status="ok").inc()
    M.TTS_PROVIDER_CALLS.labels(provider="piper", status="ok").inc()


def test_disk_gauge_can_be_set():
    M.MEDIA_DISK_USED_BYTES.labels(user_id="user-123").set(12345)
