"""Phase 5 Track B — Voice catalog, sample synthesis, voice prefs,
and per-brief narration (chaptered audio)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.exceptions import NotFoundError
from app.db.session import get_session
from app.models.media_job import MediaJob
from app.models.research_brief import ResearchBrief
from app.models.user import User
from app.models.voice import BriefNarration, UserVoicePreference
from app.services.media import audio_dir
from app.services.media.quota_check import check_and_increment, decrement_on_failure

router = APIRouter(prefix="/api", tags=["narration"])


# ─── Voice preferences ──────────────────────────────────────────────────────


class VoicePreferenceOut(BaseModel):
    default_voice_id: Optional[str]
    speed: float


class VoicePreferenceUpdate(BaseModel):
    default_voice_id: Optional[str] = None
    speed: float = Field(default=1.0, ge=0.5, le=2.0)


@router.get("/voice-preferences", response_model=VoicePreferenceOut)
async def get_voice_pref(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> VoicePreferenceOut:
    row = (
        await session.execute(
            select(UserVoicePreference).where(UserVoicePreference.user_id == user.id)
        )
    ).scalar_one_or_none()
    if row is None:
        return VoicePreferenceOut(default_voice_id=None, speed=1.0)
    return VoicePreferenceOut(
        default_voice_id=row.default_voice_id, speed=float(row.speed)
    )


@router.put("/voice-preferences", response_model=VoicePreferenceOut)
async def update_voice_pref(
    payload: VoicePreferenceUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> VoicePreferenceOut:
    row = (
        await session.execute(
            select(UserVoicePreference).where(UserVoicePreference.user_id == user.id)
        )
    ).scalar_one_or_none()
    if row is None:
        row = UserVoicePreference(
            user_id=user.id,
            default_voice_id=payload.default_voice_id,
            speed=Decimal(f"{payload.speed:.2f}"),
            last_used_at=datetime.now(timezone.utc),
        )
        session.add(row)
    else:
        row.default_voice_id = payload.default_voice_id
        row.speed = Decimal(f"{payload.speed:.2f}")
        row.last_used_at = datetime.now(timezone.utc)
    await session.commit()
    return VoicePreferenceOut(
        default_voice_id=row.default_voice_id, speed=float(row.speed)
    )


# ─── Voice samples (short cached MP3/WAV) ───────────────────────────────────


class VoiceSampleRequest(BaseModel):
    voice_id: str


@router.post("/media/voices/sample")
async def voice_sample(
    payload: VoiceSampleRequest,
    user: User = Depends(get_current_user),
) -> FileResponse:
    sample_text = (
        "This is a short sample of the selected voice. "
        "Use it to choose the best fit for your content."
    )
    sample_dir = audio_dir() / "samples"
    sample_dir.mkdir(parents=True, exist_ok=True)
    out_path = sample_dir / f"sample-{payload.voice_id}.wav"
    if not out_path.exists():
        from app.services.media.tts import synthesize

        result = await synthesize(
            sample_text, voice_id=payload.voice_id, out_path=out_path
        )
        if result is None:
            raise HTTPException(503, "No TTS provider could synthesize the sample")
    return FileResponse(str(out_path), media_type="audio/wav", filename=out_path.name)


# ─── Per-brief narration (chaptered audio) ──────────────────────────────────


class NarrateBriefRequest(BaseModel):
    voice_id: Optional[str] = None
    speed: float = Field(default=1.0, ge=0.5, le=2.0)


class BriefNarrationOut(BaseModel):
    id: uuid.UUID
    brief_id: uuid.UUID
    voice_id: Optional[str]
    speed: Optional[float]
    chapters: list[dict]
    total_duration_seconds: float
    file_path: str
    created_at: str


class NarrateBriefJobOut(BaseModel):
    job_id: uuid.UUID
    status: str


@router.post(
    "/research/briefs/{brief_id}/narrate",
    response_model=NarrateBriefJobOut,
    status_code=202,
)
async def narrate_brief_endpoint(
    brief_id: uuid.UUID,
    payload: NarrateBriefRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> NarrateBriefJobOut:
    brief = (
        await session.execute(
            select(ResearchBrief).where(
                ResearchBrief.id == brief_id,
                ResearchBrief.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if brief is None:
        raise NotFoundError(f"Brief {brief_id} not found")
    if brief.status != "complete" or not brief.brief_json:
        raise HTTPException(409, "Brief is not complete yet")

    allowed, current, cap = check_and_increment(str(user.id), "narration")
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Daily narration cap reached ({current}/{cap})",
            headers={"Retry-After": "86400"},
        )

    job = MediaJob(
        user_id=user.id,
        job_type="brief_narration",
        status="queued",
        params={
            "brief_id": str(brief_id),
            "voice_id": payload.voice_id,
            "speed": payload.speed,
        },
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    try:
        from app.workers.media import render_brief_narration_job

        render_brief_narration_job.apply_async(
            args=[str(job.id)], queue="reel", priority=4
        )
    except Exception:
        decrement_on_failure(str(user.id), "narration")
        job.status = "failed"
        job.error_message = "Failed to enqueue narration job"
        await session.commit()
        raise

    return NarrateBriefJobOut(job_id=job.id, status=job.status)


@router.get("/research/briefs/{brief_id}/narration/audio")
async def get_brief_narration_audio(
    brief_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    brief = (
        await session.execute(
            select(ResearchBrief).where(
                ResearchBrief.id == brief_id, ResearchBrief.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if brief is None:
        raise NotFoundError(f"Brief {brief_id} not found")
    p = audio_dir() / "briefs" / f"{brief_id}.mp3"
    if not p.exists():
        raise NotFoundError("Narration not yet rendered")
    return FileResponse(str(p), media_type="audio/mpeg", filename=p.name)


@router.get("/research/briefs/{brief_id}/narration", response_model=Optional[BriefNarrationOut])
async def get_brief_narration_meta(
    brief_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Optional[BriefNarrationOut]:
    row = (
        await session.execute(
            select(BriefNarration)
            .where(BriefNarration.brief_id == brief_id, BriefNarration.user_id == user.id)
            .order_by(BriefNarration.created_at.desc())
        )
    ).scalars().first()
    if row is None:
        return None
    p = audio_dir() / "briefs" / f"{brief_id}.mp3"
    total = sum(
        float(c.get("duration_seconds", 0)) for c in (row.chapters or [])
    )
    return BriefNarrationOut(
        id=row.id,
        brief_id=row.brief_id,
        voice_id=row.voice_id,
        speed=float(row.speed) if row.speed else None,
        chapters=row.chapters,
        total_duration_seconds=total,
        file_path=str(p),
        created_at=row.created_at.isoformat(),
    )
