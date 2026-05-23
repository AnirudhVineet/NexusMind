import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class DocumentCreatedResponse(BaseModel):
    document_id: uuid.UUID
    filename: str
    processing_status: str


class DocumentStatusResponse(BaseModel):
    document_id: uuid.UUID
    processing_status: str
    error_message: str | None = None
    chunk_count: int | None = None
    completed_at: datetime | None = None


class DocumentChunkResponse(BaseModel):
    id: uuid.UUID
    chunk_index: int
    text: str
    page_number: int | None
    section: str | None


class DocumentResponse(BaseModel):
    id: uuid.UUID
    filename: str
    source_type: str
    mime_type: str
    file_size_bytes: int | None
    processing_status: str
    error_message: str | None
    word_count: int | None
    chunk_count: int | None
    language: str | None
    uploaded_at: datetime
    completed_at: datetime | None
    credibility_score: float | None = None
    credibility_breakdown: dict[str, Any] | None = None
    credibility_computed_at: datetime | None = None
    source_url: str | None = None
