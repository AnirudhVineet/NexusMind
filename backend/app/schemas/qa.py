import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SearchFiltersSchema(BaseModel):
    source_type: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    topic_tag: str | None = None
    min_credibility: float | None = Field(default=None, ge=0.0, le=1.0)
    entity_id: uuid.UUID | None = None
    document_ids: list[uuid.UUID] = Field(default_factory=list)


class QARequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    conversation_id: uuid.UUID | None = None
    top_k: int = Field(default=5, ge=1, le=50)
    document_ids: list[uuid.UUID] | None = None
    filters: SearchFiltersSchema | None = None


class Citation(BaseModel):
    index: int
    chunk_id: uuid.UUID
    document_title: str
    page_number: int | None
    section: str | None
    snippet: str


class QAResponse(BaseModel):
    answer: str
    citations: list[Citation]
    confidence_score: float
    no_source_found: bool
    conversation_id: uuid.UUID | None = None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    filters: SearchFiltersSchema | None = None
    top_k: int = Field(default=10, ge=1, le=50)


class SearchResult(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    page_number: int | None
    section: str | None
    text: str
    similarity_score: float
    source_type: str
    credibility_score: float | None
    topic_tags: list[str]


class SearchResponse(BaseModel):
    results: list[SearchResult]
    cached: bool = False
    latency_ms: int = 0
