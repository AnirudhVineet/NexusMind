"""Phase 5 Track A — Pydantic schemas for the media pipeline."""
from __future__ import annotations

import uuid
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

AspectRatio = Literal["vertical", "square", "landscape"]
MusicStyle = Literal["ambient", "energetic", "quirky", "corporate", "none"]
RenderQuality = Literal["preview", "final"]
ReelLength = Literal["short", "long"]


class ReelParams(BaseModel):
    aspect_ratio: AspectRatio = "vertical"
    voice_id: Optional[str] = None
    music_style: Optional[MusicStyle] = None
    watermark: bool = True
    quality: RenderQuality = "final"
    length: ReelLength = "short"


class NarrationParams(BaseModel):
    text: str
    voice_id: Optional[str] = None
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    source_ref: Optional[str] = None


class StoryboardParams(BaseModel):
    format: Literal["pdf", "image_series", "html_slides"] = "pdf"


class CreateReelRequest(BaseModel):
    content_id: uuid.UUID
    aspect_ratio: AspectRatio = "vertical"
    voice_id: Optional[str] = None
    music_style: Optional[MusicStyle] = None
    watermark: bool = True
    quality: RenderQuality = "final"
    length: ReelLength = "short"


class CreateNarrationRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=20_000)
    voice_id: Optional[str] = None
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    source_ref: Optional[str] = None


class CreateStoryboardRequest(BaseModel):
    content_id: uuid.UUID
    format: Literal["pdf", "image_series", "html_slides"] = "pdf"


class JobCreatedResponse(BaseModel):
    job_id: uuid.UUID
    status: str


class MediaJobOut(BaseModel):
    id: uuid.UUID
    job_type: str
    status: str
    stage: Optional[str] = None
    progress_pct: int
    output_path: Optional[str] = None
    output_size_bytes: Optional[int] = None
    duration_seconds: Optional[float] = None
    cost_estimate_usd: Optional[float] = None
    error_message: Optional[str] = None
    content_id: Optional[uuid.UUID] = None
    params: dict[str, Any]
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    expires_at: Optional[str] = None


class MediaAssetOut(BaseModel):
    id: uuid.UUID
    asset_type: str
    file_path: str
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    duration_seconds: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    source_kind: str
    source_ref: Optional[str] = None
    license: Optional[str] = None
    metadata_json: dict[str, Any]
    created_at: str
