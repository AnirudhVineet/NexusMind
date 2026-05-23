import uuid
from typing import List, Optional

from pydantic import BaseModel, Field


class IntelligenceMetrics(BaseModel):
    flesch_kincaid_grade: float
    reading_minutes: int
    jargon_density: float


class KeyInsight(BaseModel):
    claim: str
    source_chunk_id: uuid.UUID
    confidence: float


class DocumentIntelligence(BaseModel):
    abstract: str = ""
    summary: List[str] = Field(default_factory=list)
    deep_dive: str = ""
    key_insights: List[KeyInsight] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    metrics: Optional[IntelligenceMetrics] = None
    computed_at: Optional[str] = None
