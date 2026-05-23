"""Phase 5 Track A — Media job API.

Endpoints (all under /api):
  POST   /api/media/reels                    — enqueue reel render
  POST   /api/media/narration                — enqueue / sync narration
  GET    /api/media/jobs/{job_id}            — poll a job (any type)
  GET    /api/media/jobs/{job_id}/stream     — SSE progress stream
  GET    /api/media/jobs/{job_id}/output     — stream the rendered file (Range supported)
  DELETE /api/media/jobs/{job_id}            — cancel/delete
  GET    /api/media/reels?content_id=        — list reels for a content row
  GET    /api/media/voices                   — voice catalog (Track B will enrich)
  GET    /api/media/quota                    — per-user daily caps + current counts
"""
from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import get_session
from app.models.generated_content import GeneratedContent
from app.models.media_job import MediaJob
from app.models.user import User
from app.schemas.media import (
    CreateNarrationRequest,
    CreateReelRequest,
    JobCreatedResponse,
    MediaJobOut,
)
from app.services.media.ffmpeg_runner import detect_ffmpeg
from app.services.media.quota_check import (
    check_and_increment,
    current_usage,
    decrement_on_failure,
)

router = APIRouter(prefix="/api/media", tags=["media"])


# ─── Serialization helpers ──────────────────────────────────────────────────


def _serialize(row: MediaJob) -> MediaJobOut:
    return MediaJobOut(
        id=row.id,
        job_type=row.job_type,
        status=row.status,
        stage=row.stage,
        progress_pct=row.progress_pct,
        output_path=row.output_path,
        output_size_bytes=row.output_size_bytes,
        duration_seconds=float(row.duration_seconds) if row.duration_seconds else None,
        cost_estimate_usd=float(row.cost_estimate_usd) if row.cost_estimate_usd else 0.0,
        error_message=row.error_message,
        content_id=row.content_id,
        params=row.params or {},
        created_at=row.created_at.isoformat(),
        started_at=row.started_at.isoformat() if row.started_at else None,
        completed_at=row.completed_at.isoformat() if row.completed_at else None,
        expires_at=row.expires_at.isoformat() if row.expires_at else None,
    )


async def _get_owned_job(
    job_id: uuid.UUID, user: User, session: AsyncSession
) -> MediaJob:
    row = (
        await session.execute(
            select(MediaJob).where(MediaJob.id == job_id, MediaJob.user_id == user.id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError(f"Media job {job_id} not found")
    return row


# ─── Reel render ────────────────────────────────────────────────────────────


@router.post(
    "/reels",
    response_model=JobCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_reel(
    payload: CreateReelRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> JobCreatedResponse:
    if not detect_ffmpeg():
        raise HTTPException(
            status_code=503,
            detail=(
                "FFmpeg not installed. Install via 'winget install Gyan.FFmpeg' "
                "or 'pip install imageio-ffmpeg', then restart the worker."
            ),
        )

    # Verify content_id is a reel script owned by this user
    cont = (
        await session.execute(
            select(GeneratedContent).where(
                GeneratedContent.id == payload.content_id,
                GeneratedContent.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if cont is None:
        raise NotFoundError(f"Content {payload.content_id} not found")
    if cont.content_type != "reel_script":
        raise ValidationError("content_id must reference a reel_script row")

    allowed, current_count, cap = check_and_increment(str(user.id), "reel")
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Daily reel cap reached ({current_count}/{cap})",
            headers={"Retry-After": "86400"},
        )

    job = MediaJob(
        user_id=user.id,
        content_id=payload.content_id,
        job_type="reel",
        status="queued",
        params={
            "aspect_ratio": payload.aspect_ratio,
            "voice_id": payload.voice_id,
            "music_style": payload.music_style,
            "watermark": payload.watermark,
            "quality": payload.quality,
            "length": payload.length,
        },
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    try:
        from app.workers.media import render_reel_job

        render_reel_job.apply_async(args=[str(job.id)], queue="reel", priority=3)
    except Exception:
        # Roll back the quota increment if we couldn't enqueue
        decrement_on_failure(str(user.id), "reel")
        job.status = "failed"
        job.error_message = "Failed to enqueue render job"
        await session.commit()
        raise

    return JobCreatedResponse(job_id=job.id, status=job.status)


# ─── Narration (Track B inline) ─────────────────────────────────────────────


@router.post(
    "/narration",
    response_model=JobCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_narration(
    payload: CreateNarrationRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> JobCreatedResponse:
    allowed, current_count, cap = check_and_increment(str(user.id), "narration")
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Daily narration cap reached ({current_count}/{cap})",
            headers={"Retry-After": "86400"},
        )

    job = MediaJob(
        user_id=user.id,
        job_type="narration",
        status="queued",
        params={
            "text": payload.text,
            "voice_id": payload.voice_id,
            "speed": payload.speed,
            "source_ref": payload.source_ref,
        },
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    try:
        from app.workers.media import render_narration_job

        render_narration_job.apply_async(
            args=[str(job.id)], queue="reel", priority=5
        )
    except Exception:
        decrement_on_failure(str(user.id), "narration")
        job.status = "failed"
        job.error_message = "Failed to enqueue narration job"
        await session.commit()
        raise

    return JobCreatedResponse(job_id=job.id, status=job.status)


# ─── Polling + streaming ────────────────────────────────────────────────────


@router.get("/jobs/{job_id}", response_model=MediaJobOut)
async def get_job(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MediaJobOut:
    row = await _get_owned_job(job_id, user, session)
    return _serialize(row)


@router.get("/jobs/{job_id}/stream")
async def stream_job(
    job_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    await _get_owned_job(job_id, user, session)  # ensure ownership before SSE

    async def event_gen():
        last_payload: Optional[str] = None
        while True:
            if await request.is_disconnected():
                return
            from app.db.session import AsyncSessionLocal

            async with AsyncSessionLocal() as s:
                row = (
                    await s.execute(
                        select(MediaJob).where(
                            MediaJob.id == job_id, MediaJob.user_id == user.id
                        )
                    )
                ).scalar_one_or_none()
                if row is None:
                    yield f"event: error\ndata: job_missing\n\n"
                    return
                payload = json.dumps(
                    {
                        "status": row.status,
                        "stage": row.stage,
                        "progress_pct": row.progress_pct,
                        "error_message": row.error_message,
                    }
                )
            if payload != last_payload:
                yield f"event: progress\ndata: {payload}\n\n"
                last_payload = payload
            if row.status in ("complete", "failed", "canceled"):
                yield f"event: done\ndata: {payload}\n\n"
                return
            await asyncio.sleep(1.5)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/jobs/{job_id}/output")
async def get_job_output(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    row = await _get_owned_job(job_id, user, session)
    if not row.output_path:
        raise NotFoundError("Output not yet available")
    p = Path(row.output_path)
    if not p.exists():
        raise NotFoundError("Output file missing on disk")
    mime = "video/mp4"
    if p.suffix.lower() in (".wav", ".mp3"):
        mime = "audio/mpeg" if p.suffix.lower() == ".mp3" else "audio/wav"
    elif p.suffix.lower() == ".png":
        mime = "image/png"
    elif p.suffix.lower() == ".pdf":
        mime = "application/pdf"
    # FileResponse handles Range requests natively
    return FileResponse(path=str(p), media_type=mime, filename=p.name)


@router.delete(
    "/jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_job(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    row = await _get_owned_job(job_id, user, session)
    if row.output_path:
        try:
            p = Path(row.output_path)
            if p.exists():
                p.unlink()
        except Exception:
            pass
    await session.delete(row)
    await session.commit()


@router.get("/reels", response_model=list[MediaJobOut])
async def list_reels(
    content_id: Optional[uuid.UUID] = Query(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[MediaJobOut]:
    stmt = (
        select(MediaJob)
        .where(MediaJob.user_id == user.id, MediaJob.job_type == "reel")
        .order_by(MediaJob.created_at.desc())
    )
    if content_id is not None:
        stmt = stmt.where(MediaJob.content_id == content_id)
    rows = (await session.execute(stmt)).scalars().all()
    return [_serialize(r) for r in rows]


@router.get("/jobs", response_model=list[MediaJobOut])
async def list_jobs(
    job_type: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    content_id: Optional[uuid.UUID] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[MediaJobOut]:
    """List media render jobs for the current user across all types.

    Supports filtering by job_type, status, or content_id, and pagination.
    """
    stmt = (
        select(MediaJob)
        .where(MediaJob.user_id == user.id)
        .order_by(MediaJob.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if job_type is not None:
        stmt = stmt.where(MediaJob.job_type == job_type)
    if status_filter is not None:
        stmt = stmt.where(MediaJob.status == status_filter)
    if content_id is not None:
        stmt = stmt.where(MediaJob.content_id == content_id)
    rows = (await session.execute(stmt)).scalars().all()
    return [_serialize(r) for r in rows]


# ─── Voice catalog + quota status ───────────────────────────────────────────


@router.get("/voices")
async def list_voices(user: User = Depends(get_current_user)) -> list[dict]:
    from app.services.media.tts import list_voices as _voices

    return await _voices()


@router.get("/quota")
async def get_quota(user: User = Depends(get_current_user)) -> dict:
    types = ["reel", "narration", "storyboard", "meme_image"]
    return {
        t: {"current": current_usage(str(user.id), t)[0], "cap": current_usage(str(user.id), t)[1]}
        for t in types
    }
