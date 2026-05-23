"""Pydantic schemas for the credibility API (Phase 2.5)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class CredibilityResponse(BaseModel):
    document_id: uuid.UUID
    score: float | None
    label: str | None
    breakdown: dict[str, Any] | None
    computed_at: datetime | None


class CredibilityWeights(BaseModel):
    recency: float
    source_type: float
    cross_source_agreement: float
    citation_density: float
