"""Phase 5 Track G — Brand kit API + media asset upload."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.exceptions import ValidationError
from app.db.session import get_session
from app.models.brandkit import BrandKit
from app.models.media_asset import MediaAsset
from app.models.user import User
from app.services.media import brandkit_dir

router = APIRouter(prefix="/api/brandkit", tags=["brandkit"])

ALLOWED_UPLOAD_MIMES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/svg+xml",
    "audio/mpeg",
    "audio/wav",
}

UPLOAD_MAX_BYTES = 5 * 1024 * 1024  # 5 MB


class BrandKitOut(BaseModel):
    primary_color: Optional[str]
    secondary_color: Optional[str]
    accent_color: Optional[str]
    font_heading: Optional[str]
    font_body: Optional[str]
    logo_asset_id: Optional[uuid.UUID]
    watermark_asset_id: Optional[uuid.UUID]
    watermark_opacity: float
    watermark_position: str
    music_style_default: Optional[str]
    subtitle_style: dict[str, Any]


class BrandKitUpdate(BaseModel):
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    accent_color: Optional[str] = None
    font_heading: Optional[str] = None
    font_body: Optional[str] = None
    logo_asset_id: Optional[uuid.UUID] = None
    watermark_asset_id: Optional[uuid.UUID] = None
    watermark_opacity: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    watermark_position: Optional[str] = None
    music_style_default: Optional[str] = None
    subtitle_style: Optional[dict[str, Any]] = None


def _serialize(row: BrandKit) -> BrandKitOut:
    return BrandKitOut(
        primary_color=row.primary_color,
        secondary_color=row.secondary_color,
        accent_color=row.accent_color,
        font_heading=row.font_heading,
        font_body=row.font_body,
        logo_asset_id=row.logo_asset_id,
        watermark_asset_id=row.watermark_asset_id,
        watermark_opacity=float(row.watermark_opacity or 0.6),
        watermark_position=row.watermark_position,
        music_style_default=row.music_style_default,
        subtitle_style=row.subtitle_style or {},
    )


@router.get("", response_model=BrandKitOut)
async def get_kit(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BrandKitOut:
    row = (
        await session.execute(
            select(BrandKit).where(BrandKit.user_id == user.id)
        )
    ).scalar_one_or_none()
    if row is None:
        # Synth a default-shaped response without writing
        return BrandKitOut(
            primary_color="#3050A0",
            secondary_color="#101018",
            accent_color="#FFD166",
            font_heading="Anton",
            font_body="Inter",
            logo_asset_id=None,
            watermark_asset_id=None,
            watermark_opacity=0.6,
            watermark_position="bottom-right",
            music_style_default="ambient",
            subtitle_style={},
        )
    return _serialize(row)


@router.patch("", response_model=BrandKitOut)
async def update_kit(
    payload: BrandKitUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BrandKitOut:
    row = (
        await session.execute(
            select(BrandKit).where(BrandKit.user_id == user.id)
        )
    ).scalar_one_or_none()
    if row is None:
        row = BrandKit(user_id=user.id)
        session.add(row)

    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "watermark_opacity" and value is not None:
            row.watermark_opacity = Decimal(f"{value:.2f}")
        else:
            setattr(row, field, value)
    row.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(row)
    return _serialize(row)


class AssetOut(BaseModel):
    id: uuid.UUID
    asset_type: str
    file_path: str
    mime_type: Optional[str]
    size_bytes: Optional[int]
    width: Optional[int]
    height: Optional[int]
    source_kind: str
    license: Optional[str]
    created_at: str


@router.post("/upload", response_model=AssetOut, status_code=status.HTTP_201_CREATED)
async def upload_asset(
    file: UploadFile = File(...),
    asset_type: str = Form(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AssetOut:
    if file.content_type not in ALLOWED_UPLOAD_MIMES:
        raise ValidationError(f"MIME type {file.content_type} not allowed")
    if asset_type not in {"brand_logo", "brand_watermark", "user_upload"}:
        raise ValidationError(f"Unsupported asset_type {asset_type}")

    contents = await file.read()
    if len(contents) > UPLOAD_MAX_BYTES:
        raise HTTPException(413, "File exceeds 5 MB limit")

    user_dir = brandkit_dir() / str(user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename or "asset").suffix or ""
    out_path = user_dir / f"{uuid.uuid4().hex}{ext}"
    out_path.write_bytes(contents)

    width: Optional[int] = None
    height: Optional[int] = None
    if (file.content_type or "").startswith("image/"):
        try:
            from PIL import Image

            with Image.open(out_path) as img:
                width, height = img.size
        except Exception:
            pass

    asset = MediaAsset(
        user_id=user.id,
        asset_type=asset_type,
        file_path=str(out_path),
        mime_type=file.content_type,
        size_bytes=len(contents),
        width=width,
        height=height,
        source_kind="uploaded",
        source_ref=file.filename,
        license="user_owned",
    )
    session.add(asset)
    await session.commit()
    await session.refresh(asset)

    return AssetOut(
        id=asset.id,
        asset_type=asset.asset_type,
        file_path=asset.file_path,
        mime_type=asset.mime_type,
        size_bytes=asset.size_bytes,
        width=asset.width,
        height=asset.height,
        source_kind=asset.source_kind,
        license=asset.license,
        created_at=asset.created_at.isoformat(),
    )


@router.get("/assets", response_model=list[AssetOut])
async def list_assets(
    asset_type: Optional[str] = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[AssetOut]:
    stmt = (
        select(MediaAsset)
        .where(MediaAsset.user_id == user.id)
        .order_by(MediaAsset.created_at.desc())
    )
    if asset_type:
        stmt = stmt.where(MediaAsset.asset_type == asset_type)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        AssetOut(
            id=a.id,
            asset_type=a.asset_type,
            file_path=a.file_path,
            mime_type=a.mime_type,
            size_bytes=a.size_bytes,
            width=a.width,
            height=a.height,
            source_kind=a.source_kind,
            license=a.license,
            created_at=a.created_at.isoformat(),
        )
        for a in rows
    ]


@router.delete(
    "/assets/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_asset(
    asset_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    a = (
        await session.execute(
            select(MediaAsset).where(
                MediaAsset.id == asset_id, MediaAsset.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if a is None:
        raise HTTPException(404, "Asset not found")
    try:
        Path(a.file_path).unlink(missing_ok=True)
    except Exception:
        pass
    await session.delete(a)
    await session.commit()
