"""Phase 5 Track D — Storyboard render API."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import get_session
from app.models.generated_content import GeneratedContent
from app.models.media_job import MediaJob
from app.models.user import User
from app.schemas.media import CreateStoryboardRequest, JobCreatedResponse
from app.services.media import storyboards_dir
from app.services.media.quota_check import (
    check_and_increment,
    decrement_on_failure,
)

router = APIRouter(prefix="/api/media", tags=["storyboards"])


@router.post(
    "/storyboards",
    response_model=JobCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_storyboard(
    payload: CreateStoryboardRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> JobCreatedResponse:
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
    if cont.content_type != "storyboard":
        raise ValidationError("content_id must reference a storyboard row")

    allowed, current, cap = check_and_increment(str(user.id), "storyboard")
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Daily storyboard cap reached ({current}/{cap})",
            headers={"Retry-After": "86400"},
        )

    job = MediaJob(
        user_id=user.id,
        content_id=payload.content_id,
        job_type="storyboard",
        status="queued",
        params={"format": payload.format},
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    try:
        from app.workers.media import render_storyboard_job

        render_storyboard_job.apply_async(
            args=[str(job.id)], queue="reel", priority=4
        )
    except Exception:
        decrement_on_failure(str(user.id), "storyboard")
        job.status = "failed"
        job.error_message = "Failed to enqueue storyboard job"
        await session.commit()
        raise

    return JobCreatedResponse(job_id=job.id, status=job.status)


@router.get("/storyboards/{job_id}/pdf")
async def get_storyboard_pdf(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    job = (
        await session.execute(
            select(MediaJob).where(
                MediaJob.id == job_id,
                MediaJob.user_id == user.id,
                MediaJob.job_type == "storyboard",
            )
        )
    ).scalar_one_or_none()
    if job is None:
        raise NotFoundError("Storyboard job not found")
    if (job.params or {}).get("format") != "pdf":
        raise HTTPException(409, "Storyboard format is not PDF")
    if not job.output_path:
        raise NotFoundError("PDF not yet rendered")
    p = Path(job.output_path)
    if not p.exists():
        raise NotFoundError("PDF file missing on disk")
    return FileResponse(str(p), media_type="application/pdf", filename=p.name)


@router.get("/storyboards/{job_id}/frames/{filename}")
async def get_storyboard_frame(
    job_id: uuid.UUID,
    filename: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    job = (
        await session.execute(
            select(MediaJob).where(
                MediaJob.id == job_id,
                MediaJob.user_id == user.id,
                MediaJob.job_type == "storyboard",
            )
        )
    ).scalar_one_or_none()
    if job is None:
        raise NotFoundError("Storyboard job not found")
    base = storyboards_dir() / str(job_id)
    safe = Path(filename).name
    p = base / safe
    if not p.exists():
        raise NotFoundError("Frame not found")
    mime = "image/png" if p.suffix.lower() == ".png" else "audio/wav"
    return FileResponse(str(p), media_type=mime, filename=p.name)


@router.get("/storyboards/{job_id}/slides")
async def get_storyboard_slides(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    job = (
        await session.execute(
            select(MediaJob).where(
                MediaJob.id == job_id,
                MediaJob.user_id == user.id,
                MediaJob.job_type == "storyboard",
            )
        )
    ).scalar_one_or_none()
    if job is None:
        raise NotFoundError("Storyboard job not found")
    if (job.params or {}).get("format") != "html_slides":
        raise HTTPException(409, "Storyboard format is not HTML slides")
    p = storyboards_dir() / str(job_id) / "index.html"
    if not p.exists():
        raise NotFoundError("Slide deck not yet rendered")
    return FileResponse(str(p), media_type="text/html", filename="index.html")


@router.get("/storyboards/{job_id}/manifest")
async def get_storyboard_manifest(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    job = (
        await session.execute(
            select(MediaJob).where(
                MediaJob.id == job_id,
                MediaJob.user_id == user.id,
                MediaJob.job_type == "storyboard",
            )
        )
    ).scalar_one_or_none()
    if job is None:
        raise NotFoundError("Storyboard job not found")
    p = storyboards_dir() / str(job_id) / "manifest.json"
    if not p.exists():
        raise NotFoundError("Manifest not available")
    return FileResponse(str(p), media_type="application/json", filename="manifest.json")
