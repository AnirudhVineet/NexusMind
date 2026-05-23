"""Prometheus /metrics endpoint.

Basic-auth gated by `METRICS_TOKEN` if set; if unset, the endpoint is open.
"""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

import app.core.metrics  # noqa: F401 — registers metrics
from app.core.config import get_settings

router = APIRouter(prefix="", tags=["metrics"])


@router.get("/metrics")
def metrics(authorization: str | None = Header(default=None)) -> Response:
    token = getattr(get_settings(), "metrics_token", "") or ""
    if token:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="metrics token required")
        provided = authorization.split(None, 1)[1].strip()
        if not secrets.compare_digest(provided, token):
            raise HTTPException(status_code=401, detail="invalid metrics token")
    payload = generate_latest()
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)
