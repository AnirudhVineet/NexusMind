"""Phase 5 Track F — Authenticated publishing endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import get_session
from app.models.generated_content import GeneratedContent
from app.models.media_job import MediaJob
from app.models.research_brief import ResearchBrief
from app.models.share_link import ShareLink
from app.models.user import User
from app.services.publish import create_share_link

router = APIRouter(prefix="/api/publish", tags=["publish"])


class CreateShareRequest(BaseModel):
    target_type: str = Field(..., pattern="^(content|media_job|brief)$")
    target_id: uuid.UUID
    expires_in_hours: Optional[int] = Field(default=None, ge=1, le=24 * 365)
    password: Optional[str] = Field(default=None, min_length=4, max_length=128)


class ShareLinkOut(BaseModel):
    id: uuid.UUID
    slug: str
    url: str
    target_type: str
    target_id: uuid.UUID
    expires_at: Optional[str]
    view_count: int
    enabled: bool
    created_at: str
    has_password: bool


def _serialize(row: ShareLink) -> ShareLinkOut:
    return ShareLinkOut(
        id=row.id,
        slug=row.slug,
        url=f"/s/{row.slug}",
        target_type=row.target_type,
        target_id=row.target_id,
        expires_at=row.expires_at.isoformat() if row.expires_at else None,
        view_count=row.view_count,
        enabled=row.enabled,
        created_at=row.created_at.isoformat(),
        has_password=bool(row.password_hash),
    )


async def _verify_user_owns_target(
    session: AsyncSession,
    user: User,
    target_type: str,
    target_id: uuid.UUID,
) -> None:
    if target_type == "content":
        row = (
            await session.execute(
                select(GeneratedContent).where(
                    GeneratedContent.id == target_id,
                    GeneratedContent.user_id == user.id,
                )
            )
        ).scalar_one_or_none()
    elif target_type == "media_job":
        row = (
            await session.execute(
                select(MediaJob).where(
                    MediaJob.id == target_id, MediaJob.user_id == user.id
                )
            )
        ).scalar_one_or_none()
    elif target_type == "brief":
        row = (
            await session.execute(
                select(ResearchBrief).where(
                    ResearchBrief.id == target_id,
                    ResearchBrief.user_id == user.id,
                )
            )
        ).scalar_one_or_none()
    else:
        raise ValidationError(f"Unknown target_type {target_type}")

    if row is None:
        raise NotFoundError(f"{target_type} {target_id} not found")


@router.post(
    "/share", response_model=ShareLinkOut, status_code=status.HTTP_201_CREATED
)
async def create_share(
    payload: CreateShareRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ShareLinkOut:
    await _verify_user_owns_target(
        session, user, payload.target_type, payload.target_id
    )
    expires_at = None
    if payload.expires_in_hours:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=payload.expires_in_hours)
    link = await create_share_link(
        session=session,
        user_id=user.id,
        target_type=payload.target_type,
        target_id=payload.target_id,
        expires_at=expires_at,
        password=payload.password,
    )
    return _serialize(link)


@router.get("/share", response_model=list[ShareLinkOut])
async def list_shares(
    target_id: Optional[uuid.UUID] = Query(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ShareLinkOut]:
    stmt = (
        select(ShareLink)
        .where(ShareLink.user_id == user.id)
        .order_by(ShareLink.created_at.desc())
    )
    if target_id is not None:
        stmt = stmt.where(ShareLink.target_id == target_id)
    rows = (await session.execute(stmt)).scalars().all()
    return [_serialize(r) for r in rows]


@router.delete(
    "/share/{share_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def revoke_share(
    share_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    row = (
        await session.execute(
            select(ShareLink).where(
                ShareLink.id == share_id, ShareLink.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Share link not found")
    await session.delete(row)
    await session.commit()


class BundleRequest(BaseModel):
    target_type: str = Field(..., pattern="^(content|media_job)$")
    target_id: uuid.UUID


@router.post("/bundle")
async def bundle_target(
    payload: BundleRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    """Synchronously zip up all relevant outputs for a target."""
    from pathlib import Path

    from app.services.publish import bundle_export

    await _verify_user_owns_target(
        session, user, payload.target_type, payload.target_id
    )
    files: list[tuple[str, Path]] = []
    extra: dict[str, str] = {}

    if payload.target_type == "content":
        c = (
            await session.execute(
                select(GeneratedContent).where(GeneratedContent.id == payload.target_id)
            )
        ).scalar_one()
        if c.file_path and Path(c.file_path).exists():
            files.append((Path(c.file_path).name, Path(c.file_path)))
        if isinstance(c.content_json, dict):
            import json

            extra["content.json"] = json.dumps(c.content_json, indent=2)
    elif payload.target_type == "media_job":
        m = (
            await session.execute(
                select(MediaJob).where(MediaJob.id == payload.target_id)
            )
        ).scalar_one()
        if m.output_path and Path(m.output_path).exists():
            files.append((Path(m.output_path).name, Path(m.output_path)))

    out_path = bundle_export(
        target_type=payload.target_type,
        target_id=payload.target_id,
        files=files,
        extra_text=extra,
    )
    return FileResponse(
        str(out_path),
        media_type="application/zip",
        filename=out_path.name,
    )
