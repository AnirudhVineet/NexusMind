"""Research Assistant API — Phase 4 Track B.

POST   /api/research/briefs              — create a new research brief
GET    /api/research/briefs/{id}         — fetch a single brief
GET    /api/research/briefs              — list briefs (paginated)
DELETE /api/research/briefs/{id}         — delete a brief + cached exports
GET    /api/research/briefs/{id}/export  — export as md | json | pdf
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import get_session
from app.models.research_brief import ResearchBrief as ResearchBriefModel
from app.models.user import User

router = APIRouter(prefix="/api", tags=["research"])


# ─── Pydantic schemas ────────────────────────────────────────────────────────


class CreateBriefRequest(BaseModel):
    topic: str


class CreateBriefResponse(BaseModel):
    id: uuid.UUID
    status: str


class BriefOut(BaseModel):
    id: uuid.UUID
    topic: str
    status: str
    brief_json: Optional[dict]
    exported_paths: dict
    created_at: str
    completed_at: Optional[str]
    error_message: Optional[str]


def _serialize(row: ResearchBriefModel) -> BriefOut:
    return BriefOut(
        id=row.id,
        topic=row.topic,
        status=row.status,
        brief_json=row.brief_json,
        exported_paths=row.exported_paths or {},
        created_at=row.created_at.isoformat(),
        completed_at=row.completed_at.isoformat() if row.completed_at else None,
        error_message=row.error_message,
    )


async def _get_owned(
    brief_id: uuid.UUID,
    user: User,
    session: AsyncSession,
) -> ResearchBriefModel:
    row = (
        await session.execute(
            select(ResearchBriefModel).where(
                ResearchBriefModel.id == brief_id,
                ResearchBriefModel.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Research brief not found")
    return row


# ─── Create ──────────────────────────────────────────────────────────────────


@router.post(
    "/research/briefs",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=CreateBriefResponse,
)
async def create_brief(
    body: CreateBriefRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CreateBriefResponse:
    topic = body.topic.strip()
    if not topic:
        raise ValidationError("topic must not be empty")

    row = ResearchBriefModel(
        user_id=current_user.id,
        topic=topic,
        status="queued",
        brief_json=None,
        exported_paths={},
    )
    session.add(row)
    await session.flush()  # assigns id via server_default
    await session.refresh(row)
    brief_id = row.id
    await session.commit()

    from app.workers.research import generate_research_brief_task

    generate_research_brief_task.apply_async(args=[str(brief_id)])

    return CreateBriefResponse(id=brief_id, status="queued")


# ─── Get one ─────────────────────────────────────────────────────────────────


@router.get("/research/briefs/{brief_id}", response_model=BriefOut)
async def get_brief(
    brief_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BriefOut:
    row = await _get_owned(brief_id, current_user, session)
    return _serialize(row)


# ─── List ────────────────────────────────────────────────────────────────────


class BriefListResponse(BaseModel):
    items: list[BriefOut]
    total: int


@router.get("/research/briefs", response_model=BriefListResponse)
async def list_briefs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BriefListResponse:
    from sqlalchemy import func

    offset = (page - 1) * page_size

    total = (
        await session.execute(
            select(func.count(ResearchBriefModel.id)).where(
                ResearchBriefModel.user_id == current_user.id
            )
        )
    ).scalar_one()

    rows = (
        await session.execute(
            select(ResearchBriefModel)
            .where(ResearchBriefModel.user_id == current_user.id)
            .order_by(ResearchBriefModel.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
    ).scalars().all()

    return BriefListResponse(items=[_serialize(r) for r in rows], total=int(total or 0))


# ─── Delete ──────────────────────────────────────────────────────────────────


@router.delete(
    "/research/briefs/{brief_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_brief(
    brief_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    row = await _get_owned(brief_id, current_user, session)

    # Remove any cached export files
    for _fmt, path_str in (row.exported_paths or {}).items():
        try:
            Path(path_str).unlink(missing_ok=True)
        except Exception:
            pass

    await session.delete(row)
    await session.commit()


# ─── Export ──────────────────────────────────────────────────────────────────


def _exports_dir() -> Path:
    settings = get_settings()
    exports = Path(settings.storage_dir).resolve() / "exports" / "research"
    exports.mkdir(parents=True, exist_ok=True)
    return exports


def _build_markdown(data: dict) -> str:
    lines: list[str] = []
    topic = data.get("topic", "Research Brief")
    lines.append(f"# {topic}\n")

    exec_summary = data.get("executive_summary", "")
    if exec_summary:
        lines.append("## Executive Summary\n")
        lines.append(exec_summary + "\n")

    key_args = data.get("key_arguments", [])
    if key_args:
        lines.append("## Key Arguments\n")
        for i, arg in enumerate(key_args, 1):
            claim = arg.get("claim", "")
            stance = arg.get("stance", "")
            evidence = ", ".join(arg.get("evidence_chunk_ids", []))
            lines.append(f"**{i}. [{stance.upper()}]** {claim}")
            if evidence:
                lines.append(f"   *Evidence:* {evidence}")
            lines.append("")

    counterargs = data.get("counterarguments", [])
    if counterargs:
        lines.append("## Counterarguments\n")
        for i, arg in enumerate(counterargs, 1):
            claim = arg.get("claim", "")
            evidence = ", ".join(arg.get("evidence_chunk_ids", []))
            lines.append(f"**{i}.** {claim}")
            if evidence:
                lines.append(f"   *Evidence:* {evidence}")
            lines.append("")

    gaps = data.get("knowledge_gaps", [])
    if gaps:
        lines.append("## Knowledge Gaps\n")
        for gap in gaps:
            lines.append(f"- {gap}")
        lines.append("")

    reading = data.get("recommended_reading", [])
    if reading:
        lines.append("## Recommended Reading\n")
        for item in reading:
            title = item.get("document_title", "")
            reason = item.get("reason", "")
            lines.append(f"- **{title}** — {reason}")
        lines.append("")

    confidence = data.get("confidence")
    if confidence is not None:
        lines.append(f"---\n*Confidence: {confidence:.0%}*\n")

    return "\n".join(lines)


def _build_pdf(data: dict, output_path: Path) -> None:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=inch,
        rightMargin=inch,
        topMargin=inch,
        bottomMargin=inch,
    )

    story = []
    topic = data.get("topic", "Research Brief")
    story.append(Paragraph(topic, styles["Title"]))
    story.append(Spacer(1, 0.2 * inch))

    exec_summary = data.get("executive_summary", "")
    if exec_summary:
        story.append(Paragraph("Executive Summary", styles["Heading2"]))
        story.append(Paragraph(exec_summary, styles["BodyText"]))
        story.append(Spacer(1, 0.15 * inch))

    key_args = data.get("key_arguments", [])
    if key_args:
        story.append(Paragraph("Key Arguments", styles["Heading2"]))
        for i, arg in enumerate(key_args, 1):
            claim = arg.get("claim", "")
            stance = arg.get("stance", "")
            text = f"{i}. [{stance.upper()}] {claim}"
            story.append(Paragraph(text, styles["BodyText"]))
        story.append(Spacer(1, 0.15 * inch))

    counterargs = data.get("counterarguments", [])
    if counterargs:
        story.append(Paragraph("Counterarguments", styles["Heading2"]))
        for i, arg in enumerate(counterargs, 1):
            claim = arg.get("claim", "")
            story.append(Paragraph(f"{i}. {claim}", styles["BodyText"]))
        story.append(Spacer(1, 0.15 * inch))

    gaps = data.get("knowledge_gaps", [])
    if gaps:
        story.append(Paragraph("Knowledge Gaps", styles["Heading2"]))
        for gap in gaps:
            story.append(Paragraph(f"• {gap}", styles["BodyText"]))
        story.append(Spacer(1, 0.15 * inch))

    reading = data.get("recommended_reading", [])
    if reading:
        story.append(Paragraph("Recommended Reading", styles["Heading2"]))
        for item in reading:
            title = item.get("document_title", "")
            reason = item.get("reason", "")
            story.append(Paragraph(f"• {title} — {reason}", styles["BodyText"]))
        story.append(Spacer(1, 0.15 * inch))

    confidence = data.get("confidence")
    if confidence is not None:
        story.append(Paragraph(f"Confidence: {confidence:.0%}", styles["Italic"]))

    doc.build(story)


@router.get("/research/briefs/{brief_id}/export")
async def export_brief(
    brief_id: uuid.UUID,
    format: str = Query(default="md", regex="^(md|json|pdf)$"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    row = await _get_owned(brief_id, current_user, session)

    if row.brief_json is None:
        raise ValidationError("Brief is not yet complete — cannot export")

    exports_dir = _exports_dir()
    cache_path = exports_dir / f"{brief_id}.{format}"

    # Serve from cache if available
    if not cache_path.exists():
        if format == "json":
            cache_path.write_text(json.dumps(row.brief_json, indent=2), encoding="utf-8")
        elif format == "md":
            cache_path.write_text(_build_markdown(row.brief_json), encoding="utf-8")
        elif format == "pdf":
            _build_pdf(row.brief_json, cache_path)

        # Persist the export path on the row (best-effort, non-blocking)
        try:
            updated_paths = dict(row.exported_paths or {})
            updated_paths[format] = str(cache_path)
            row.exported_paths = updated_paths
            await session.commit()
        except Exception:
            pass

    media_type_map = {
        "md": "text/markdown",
        "json": "application/json",
        "pdf": "application/pdf",
    }
    filename_map = {
        "md": f"brief_{brief_id}.md",
        "json": f"brief_{brief_id}.json",
        "pdf": f"brief_{brief_id}.pdf",
    }

    return FileResponse(
        path=str(cache_path),
        media_type=media_type_map[format],
        filename=filename_map[format],
    )
