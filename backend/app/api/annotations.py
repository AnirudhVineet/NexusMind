"""Notes & annotation endpoints — Phase 3.5 / 3.4.

POST   /api/annotations            — create a highlight / note
GET    /api/annotations            — list, filterable by document/tag/date
GET    /api/annotations/export     — export all annotations as markdown or CSV
PATCH  /api/annotations/{id}       — edit note, tags, or color
DELETE /api/annotations/{id}

POST   /api/notes/highlight        — browser extension: save a selection from a URL
                                     (creates a stub Document if URL is new)
"""
from __future__ import annotations

import csv
import hashlib
import io
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import get_session
from app.models.annotation import ANNOTATION_COLORS, Annotation
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.user import User

router = APIRouter(prefix="/api", tags=["annotations"])


# ─── schemas ──────────────────────────────────────────────────────────────────

class AnnotationCreate(BaseModel):
    document_id: uuid.UUID
    chunk_id: uuid.UUID | None = None
    highlight_text: str = Field(min_length=1, max_length=10_000)
    char_start: int | None = None
    char_end: int | None = None
    note: str | None = None
    tags: list[str] = Field(default_factory=list)
    color: str = "yellow"


class AnnotationUpdate(BaseModel):
    note: str | None = None
    tags: list[str] | None = None
    color: str | None = None


class AnnotationOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    document_filename: str
    chunk_id: uuid.UUID | None
    insight_entity_id: uuid.UUID | None
    highlight_text: str
    char_start: int | None
    char_end: int | None
    note: str | None
    tags: list[str]
    color: str
    created_at: str
    updated_at: str


def _serialize(ann: Annotation, filename: str) -> AnnotationOut:
    return AnnotationOut(
        id=ann.id,
        document_id=ann.document_id,
        document_filename=filename,
        chunk_id=ann.chunk_id,
        insight_entity_id=ann.insight_entity_id,
        highlight_text=ann.highlight_text,
        char_start=ann.char_start,
        char_end=ann.char_end,
        note=ann.note,
        tags=list(ann.tags or []),
        color=ann.color,
        created_at=ann.created_at.isoformat(),
        updated_at=ann.updated_at.isoformat(),
    )


def _enqueue_projection(annotation_id: uuid.UUID) -> None:
    from app.workers.annotations import project_annotation_task

    project_annotation_task.apply_async(args=[str(annotation_id)])


# ─── create ───────────────────────────────────────────────────────────────────

@router.post(
    "/annotations",
    status_code=status.HTTP_201_CREATED,
    response_model=AnnotationOut,
)
async def create_annotation(
    body: AnnotationCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AnnotationOut:
    if body.color not in ANNOTATION_COLORS:
        raise ValidationError(f"Invalid color. Allowed: {', '.join(ANNOTATION_COLORS)}")

    doc = (
        await session.execute(
            select(Document).where(
                Document.id == body.document_id,
                Document.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        raise NotFoundError("Document not found")

    if body.chunk_id is not None:
        chunk = (
            await session.execute(
                select(Chunk).where(
                    Chunk.id == body.chunk_id,
                    Chunk.document_id == body.document_id,
                )
            )
        ).scalar_one_or_none()
        if chunk is None:
            raise ValidationError("chunk_id does not belong to the given document")

    ann = Annotation(
        user_id=current_user.id,
        document_id=body.document_id,
        chunk_id=body.chunk_id,
        highlight_text=body.highlight_text.strip(),
        char_start=body.char_start,
        char_end=body.char_end,
        note=(body.note.strip() if body.note else None) or None,
        tags=[t.strip() for t in body.tags if t.strip()],
        color=body.color,
    )
    session.add(ann)
    await session.commit()
    await session.refresh(ann)

    _enqueue_projection(ann.id)
    return _serialize(ann, doc.filename)


# ─── list ─────────────────────────────────────────────────────────────────────

@router.get("/annotations", response_model=list[AnnotationOut])
async def list_annotations(
    document_id: uuid.UUID | None = Query(default=None),
    tag: str | None = Query(default=None),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    limit: int = Query(default=500, ge=1, le=2000),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[AnnotationOut]:
    stmt = (
        select(Annotation, Document.filename)
        .join(Document, Document.id == Annotation.document_id)
        .where(Annotation.user_id == current_user.id)
        .order_by(Annotation.created_at.desc())
        .limit(limit)
    )
    if document_id is not None:
        stmt = stmt.where(Annotation.document_id == document_id)
    if tag:
        stmt = stmt.where(Annotation.tags.any(tag))
    if from_date is not None:
        stmt = stmt.where(Annotation.created_at >= datetime.combine(from_date, datetime.min.time()))
    if to_date is not None:
        stmt = stmt.where(Annotation.created_at <= datetime.combine(to_date, datetime.max.time()))

    rows = (await session.execute(stmt)).all()
    return [_serialize(ann, filename) for ann, filename in rows]


# ─── export ───────────────────────────────────────────────────────────────────

@router.get("/annotations/export")
async def export_annotations(
    format: str = Query(default="md", pattern="^(md|csv)$"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    rows = (
        await session.execute(
            select(Annotation, Document.filename)
            .join(Document, Document.id == Annotation.document_id)
            .where(Annotation.user_id == current_user.id)
            .order_by(Document.filename.asc(), Annotation.created_at.asc())
        )
    ).all()

    if format == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            ["created_at", "document", "highlight", "note", "tags", "color"]
        )
        for ann, filename in rows:
            writer.writerow(
                [
                    ann.created_at.isoformat(),
                    filename,
                    ann.highlight_text,
                    ann.note or "",
                    "; ".join(ann.tags or []),
                    ann.color,
                ]
            )
        return Response(
            content=buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="annotations.csv"'},
        )

    # markdown — grouped by document
    lines: list[str] = ["# Annotations Export", ""]
    current_doc: str | None = None
    for ann, filename in rows:
        if filename != current_doc:
            lines.append(f"\n## {filename}\n")
            current_doc = filename
        lines.append(f"> {ann.highlight_text}")
        if ann.note:
            lines.append(f"\n{ann.note}")
        meta: list[str] = [ann.created_at.date().isoformat()]
        if ann.tags:
            meta.append("tags: " + ", ".join(ann.tags))
        lines.append(f"\n*{' · '.join(meta)}*\n")
    return Response(
        content="\n".join(lines),
        media_type="text/markdown",
        headers={"Content-Disposition": 'attachment; filename="annotations.md"'},
    )


# ─── update / delete ──────────────────────────────────────────────────────────

async def _get_owned(
    annotation_id: uuid.UUID, user: User, session: AsyncSession
) -> Annotation:
    ann = (
        await session.execute(
            select(Annotation).where(
                Annotation.id == annotation_id,
                Annotation.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if ann is None:
        raise NotFoundError("Annotation not found")
    return ann


@router.patch("/annotations/{annotation_id}", response_model=AnnotationOut)
async def update_annotation(
    annotation_id: uuid.UUID,
    body: AnnotationUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AnnotationOut:
    ann = await _get_owned(annotation_id, current_user, session)

    note_changed = False
    if body.note is not None:
        new_note = body.note.strip() or None
        note_changed = new_note != ann.note
        ann.note = new_note
    if body.tags is not None:
        ann.tags = [t.strip() for t in body.tags if t.strip()]
    if body.color is not None:
        if body.color not in ANNOTATION_COLORS:
            raise ValidationError(
                f"Invalid color. Allowed: {', '.join(ANNOTATION_COLORS)}"
            )
        ann.color = body.color
    ann.updated_at = datetime.now(timezone.utc)

    await session.commit()
    await session.refresh(ann)

    if note_changed:
        _enqueue_projection(ann.id)

    doc = await session.get(Document, ann.document_id)
    return _serialize(ann, doc.filename if doc else "")


@router.delete(
    "/annotations/{annotation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_annotation(
    annotation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    ann = await _get_owned(annotation_id, current_user, session)
    await session.delete(ann)
    await session.commit()


# ─── Browser extension: save selection ────────────────────────────────────────

class HighlightRequest(BaseModel):
    url: str
    page_title: str
    selected_text: str = Field(min_length=1, max_length=10_000)
    context_text: str | None = None  # surrounding sentences for context
    note: str | None = None
    tags: list[str] = Field(default_factory=list)


@router.post(
    "/notes/highlight",
    status_code=status.HTTP_201_CREATED,
    response_model=AnnotationOut,
)
async def save_highlight(
    body: HighlightRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AnnotationOut:
    """Browser extension endpoint: persist a text selection from any web page.

    If a Document for the given URL already exists it is reused; otherwise a
    stub Document is created so the annotation has a valid document_id.
    """
    from app.services.storage import StorageService

    # find or create a stub document for this URL
    url_hash = hashlib.sha256(body.url.encode()).hexdigest()
    doc = (
        await session.execute(
            select(Document).where(
                Document.user_id == current_user.id,
                Document.content_hash == url_hash,
            )
        )
    ).scalar_one_or_none()

    if doc is None:
        stub_text = f"# {body.page_title}\n\nSource: {body.url}\n"
        data = stub_text.encode("utf-8")
        storage = StorageService()
        doc = Document(
            user_id=current_user.id,
            filename=body.page_title[:255] or body.url,
            source_type="web",
            mime_type="text/plain",
            file_size_bytes=len(data),
            content_hash=url_hash,
            storage_path="placeholder",
            source_url=body.url,
            ingestion_metadata={"extension_highlight_stub": True},
            processing_status="stub",
        )
        session.add(doc)
        await session.flush()
        storage_path = f"{current_user.id}/{doc.id}/raw.txt"
        await storage.upload(storage_path, data, "text/plain")
        doc.storage_path = storage_path
        await session.commit()
        await session.refresh(doc)

    ann = Annotation(
        user_id=current_user.id,
        document_id=doc.id,
        highlight_text=body.selected_text.strip(),
        note=(body.note.strip() if body.note else None) or None,
        tags=[t.strip() for t in body.tags if t.strip()],
        color="yellow",
    )
    session.add(ann)
    await session.commit()
    await session.refresh(ann)

    _enqueue_projection(ann.id)
    return _serialize(ann, doc.filename)
