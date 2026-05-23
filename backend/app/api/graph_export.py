"""Graph export API endpoints — Phase 4 Track E.

POST   /api/graph/export                 — request a new export (sync or async)
GET    /api/graph/exports/{job_id}       — poll job status
GET    /api/graph/exports/{job_id}/download — stream the exported file
GET    /api/graph/exports               — list recent exports for the user
DELETE /api/graph/exports/{job_id}       — cancel / delete an export
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import get_session
from app.db.sync_session import get_sync_session
from app.models.entity import Entity
from app.models.graph_export import FORMATS, GraphExport
from app.models.user import User
from app.services.graph_export import SYNC_THRESHOLD, load_subgraph, serialize_graph

router = APIRouter(prefix="/api", tags=["graph"])


# ─── schemas ──────────────────────────────────────────────────────────────────


class ExportRequest(BaseModel):
    format: str
    filters: dict = {}


class ExportJobOut(BaseModel):
    id: uuid.UUID
    format: str
    filters: dict
    status: str
    file_size_bytes: int | None
    created_at: str
    completed_at: str | None
    expires_at: str
    download_url: str | None  # "/api/graph/exports/{id}/download" when complete


# ─── helpers ──────────────────────────────────────────────────────────────────


def _job_out(job: GraphExport) -> ExportJobOut:
    return ExportJobOut(
        id=job.id,
        format=job.format,
        filters=job.filters,
        status=job.status,
        file_size_bytes=job.file_size_bytes,
        created_at=job.created_at.isoformat(),
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        expires_at=job.expires_at.isoformat(),
        download_url=(
            f"/api/graph/exports/{job.id}/download" if job.status == "complete" else None
        ),
    )


async def _get_owned_job(
    job_id: uuid.UUID, user: User, session: AsyncSession
) -> GraphExport:
    job = (
        await session.execute(
            select(GraphExport).where(
                GraphExport.id == job_id,
                GraphExport.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if job is None:
        raise NotFoundError("Export job not found")
    return job


def _export_dir() -> Path:
    settings = get_settings()
    data_dir = Path(settings.storage_dir)
    return data_dir / "exports" / "graph"


# ─── POST /api/graph/export ───────────────────────────────────────────────────


@router.post("/graph/export")
async def request_export(
    body: ExportRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if body.format not in FORMATS:
        raise ValidationError(
            f"Unsupported format {body.format!r}. Must be one of: {FORMATS}"
        )

    # Count entities to decide sync vs async path.
    entity_count: int = (
        await session.execute(
            select(func.count(Entity.id)).where(Entity.user_id == current_user.id)
        )
    ).scalar_one()

    if entity_count < SYNC_THRESHOLD:
        # ── synchronous path ──────────────────────────────────────────────────
        job_id = uuid.uuid4()
        output_dir = _export_dir()
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / f"{job_id}.{body.format}")

        sync_session = get_sync_session()
        try:
            graph = load_subgraph(current_user.id, sync_session, body.filters)
            file_size = serialize_graph(graph, body.format, output_path)
        finally:
            sync_session.close()

        now = datetime.now(timezone.utc)
        job = GraphExport(
            id=job_id,
            user_id=current_user.id,
            format=body.format,
            filters=body.filters,
            file_path=output_path,
            file_size_bytes=file_size,
            status="complete",
            completed_at=now,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)

        response.headers["X-Export-Mode"] = "sync"
        return _job_out(job)

    else:
        # ── asynchronous path ─────────────────────────────────────────────────
        job = GraphExport(
            user_id=current_user.id,
            format=body.format,
            filters=body.filters,
            status="pending",
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)

        from app.workers.graph_export import graph_export_task

        graph_export_task.apply_async(args=[str(job.id)])

        response.headers["X-Export-Mode"] = "async"
        return {"job_id": str(job.id)}


# ─── GET /api/graph/exports/{job_id} ─────────────────────────────────────────


@router.get("/graph/exports/{job_id}", response_model=ExportJobOut)
async def get_export_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ExportJobOut:
    job = await _get_owned_job(job_id, current_user, session)
    return _job_out(job)


# ─── GET /api/graph/exports/{job_id}/download ────────────────────────────────


@router.get("/graph/exports/{job_id}/download")
async def download_export(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    job = await _get_owned_job(job_id, current_user, session)

    if job.status != "complete":
        raise ValidationError(f"Export is not complete (status={job.status})")

    now = datetime.now(timezone.utc)
    if job.expires_at.replace(tzinfo=timezone.utc) <= now:
        raise ValidationError("Export has expired")

    if not job.file_path or not Path(job.file_path).exists():
        raise NotFoundError("Export file not found on disk")

    file_size = job.file_size_bytes or 0
    media_type_map = {
        "json": "application/json",
        "csv": "application/zip",
        "graphml": "application/xml",
        "gexf": "application/xml",
    }
    media_type = media_type_map.get(job.format, "application/octet-stream")
    filename = f"graph_export_{job.id}.{job.format}"
    if job.format == "csv":
        filename = f"graph_export_{job.id}.zip"

    headers: dict[str, str] = {}
    if file_size > 1_000_000:
        headers["Content-Encoding"] = "gzip"

    return FileResponse(
        path=job.file_path,
        media_type=media_type,
        filename=filename,
        headers=headers,
    )


# ─── GET /api/graph/exports ───────────────────────────────────────────────────


@router.get("/graph/exports", response_model=list[ExportJobOut])
async def list_exports(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ExportJobOut]:
    jobs = (
        await session.execute(
            select(GraphExport)
            .where(GraphExport.user_id == current_user.id)
            .order_by(GraphExport.created_at.desc())
            .limit(20)
        )
    ).scalars().all()
    return [_job_out(j) for j in jobs]


# ─── DELETE /api/graph/exports/{job_id} ──────────────────────────────────────


@router.delete(
    "/graph/exports/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_export(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    job = await _get_owned_job(job_id, current_user, session)

    if job.file_path:
        try:
            Path(job.file_path).unlink(missing_ok=True)
        except Exception:
            pass

    await session.delete(job)
    await session.commit()
