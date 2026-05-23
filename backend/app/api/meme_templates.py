"""Phase 5 Track C — Meme templates catalog + per-template preview endpoint."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.models.user import User
from app.services.media.meme_renderer import TEMPLATES_DIR, list_templates

router = APIRouter(prefix="/api/media", tags=["meme_templates"])


class RegionOut(BaseModel):
    id: str
    x: float
    y: float
    w: float
    h: float
    align: str | None = None
    font_size_pct: float | None = None
    color: str | None = None
    outline: str | None = None
    uppercase: bool | None = None


class TemplateOut(BaseModel):
    key: str
    name: str
    layout: str
    regions: list[RegionOut]
    has_image: bool
    license: str


@router.get("/meme-templates", response_model=list[TemplateOut])
async def get_meme_templates(user: User = Depends(get_current_user)) -> list[TemplateOut]:
    return [TemplateOut(**t) for t in list_templates()]


@router.get("/meme-templates/{key}/preview")
async def get_template_preview(
    key: str,
    user: User = Depends(get_current_user),
) -> FileResponse:
    normalized = key.lower().replace(" ", "_").replace(".png", "")
    path = TEMPLATES_DIR / f"{normalized}.png"
    if not path.exists():
        raise HTTPException(404, f"Template {key} has no preview image")
    return FileResponse(str(path), media_type="image/png", filename=path.name)


class RenderMemeRequest(BaseModel):
    template_key: str
    panel_texts: dict[str, str]
    custom_background_prompt: str | None = None


class RenderMemeResponse(BaseModel):
    file_path: str
    url: str


@router.post("/meme-render", response_model=RenderMemeResponse)
async def render_meme_endpoint(
    payload: RenderMemeRequest,
    user: User = Depends(get_current_user),
) -> RenderMemeResponse:
    """Standalone meme render. Phase 4's POST /api/content/{id}/render_meme
    keeps the legacy per-content path; this endpoint is for live Studio
    previews where there is no DB row yet.
    """
    from app.services.media.meme_renderer import render_custom_meme, render_meme

    if payload.template_key.lower() == "custom":
        if not payload.custom_background_prompt:
            raise HTTPException(422, "custom_background_prompt required for custom memes")
        main_text = payload.panel_texts.get("main", "")
        out = await render_custom_meme(main_text, payload.custom_background_prompt)
    else:
        out = render_meme(payload.template_key, dict(payload.panel_texts))

    if out is None:
        raise HTTPException(500, "Failed to render meme")
    return RenderMemeResponse(file_path=str(out), url=f"/api/media/meme-image/{out.name}")


@router.get("/meme-image/{filename}")
async def get_rendered_meme(
    filename: str,
    user: User = Depends(get_current_user),
) -> FileResponse:
    from app.services.media import memes_dir

    # Path-traversal guard
    name = Path(filename).name
    p = memes_dir() / name
    if not p.exists():
        raise HTTPException(404, "Meme image not found")
    return FileResponse(str(p), media_type="image/png", filename=name)
