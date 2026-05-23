"""Phase 5 Track F — Public (unauthenticated) share viewer endpoints.

These routes live OUTSIDE /api so they can be opened by anyone with the
slug, no JWT required. The public viewer renders only sanitized data and
strips any PII fields before responding.
"""
from __future__ import annotations


from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.services.publish import (
    record_view,
    render_og_thumbnail,
    render_public_data,
    resolve_link,
    resolve_target_file,
    verify_password,
)

router = APIRouter(prefix="/s", tags=["public_share"])

OG_CACHE: dict[str, bytes] = {}


class PublicViewResponse(BaseModel):
    target_type: str
    requires_password: bool = False
    data: dict | None = None


@router.get("/{slug}/info", response_model=PublicViewResponse)
async def public_info(
    slug: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> PublicViewResponse:
    link = await resolve_link(session, slug)
    if link is None:
        raise HTTPException(404, "Share link not found or expired")
    if link.password_hash:
        # Check cookie for prior unlock
        cookie = request.cookies.get(f"nm_share_{slug}")
        if cookie != "ok":
            return PublicViewResponse(
                target_type=link.target_type, requires_password=True, data=None
            )
    await record_view(session, link)
    data = await render_public_data(session, link)
    return PublicViewResponse(
        target_type=link.target_type, requires_password=False, data=data
    )


class UnlockRequest(BaseModel):
    password: str


@router.post("/{slug}/unlock")
async def public_unlock(
    slug: str,
    payload: UnlockRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict:
    link = await resolve_link(session, slug)
    if link is None:
        raise HTTPException(404, "Share link not found or expired")
    if not link.password_hash:
        return {"ok": True}
    if not verify_password(payload.password, link.password_hash):
        raise HTTPException(403, "Incorrect password")
    response.set_cookie(
        key=f"nm_share_{slug}",
        value="ok",
        max_age=60 * 60 * 24,
        httponly=True,
        samesite="lax",
        secure=False,  # set True behind TLS termination
    )
    return {"ok": True}


@router.get("/{slug}/asset")
async def public_asset(
    slug: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    link = await resolve_link(session, slug)
    if link is None:
        raise HTTPException(404, "Share link not found or expired")
    if link.password_hash:
        if request.cookies.get(f"nm_share_{slug}") != "ok":
            raise HTTPException(403, "Password required")
    path = await resolve_target_file(session, link)
    if path is None:
        raise HTTPException(404, "Asset not available")
    mime = "application/octet-stream"
    suf = path.suffix.lower()
    if suf == ".mp4":
        mime = "video/mp4"
    elif suf in (".wav",):
        mime = "audio/wav"
    elif suf == ".mp3":
        mime = "audio/mpeg"
    elif suf == ".png":
        mime = "image/png"
    elif suf == ".pdf":
        mime = "application/pdf"
    return FileResponse(str(path), media_type=mime, filename=path.name)


@router.get("/{slug}/og.png")
async def public_og(
    slug: str,
    session: AsyncSession = Depends(get_session),
) -> Response:
    cached = OG_CACHE.get(slug)
    if cached is not None:
        return Response(content=cached, media_type="image/png")
    link = await resolve_link(session, slug)
    if link is None:
        raise HTTPException(404, "Share link not found or expired")
    data = await render_public_data(session, link)
    png = render_og_thumbnail(link, data)
    OG_CACHE[slug] = png
    return Response(content=png, media_type="image/png")
