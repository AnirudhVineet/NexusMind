"""Document Intelligence API.

GET returns the stored JSONB. POST triggers a recompute via Celery.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.session import get_session
from app.models.document import Document
from app.models.user import User
from app.schemas.intelligence import DocumentIntelligence

router = APIRouter(prefix="/api/documents", tags=["intelligence"])


def _stored_or_empty(doc: Document) -> dict:
    payload = dict(doc.intelligence or {})
    if doc.intelligence_computed_at is not None:
        payload["computed_at"] = doc.intelligence_computed_at.isoformat()
    return payload


@router.get("/{document_id}/intelligence", response_model=DocumentIntelligence)
async def get_intelligence(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DocumentIntelligence:
    doc = (
        await session.execute(
            select(Document).where(
                Document.id == document_id, Document.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="document not found")
    return DocumentIntelligence.model_validate(_stored_or_empty(doc))


@router.post("/{document_id}/intelligence", status_code=status.HTTP_202_ACCEPTED)
async def recompute_intelligence(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    doc = (
        await session.execute(
            select(Document).where(
                Document.id == document_id, Document.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="document not found")

    # Clear any prior idempotency record so the task actually re-runs.
    from sqlalchemy import delete

    from app.models.task_run import TaskRun

    await session.execute(
        delete(TaskRun).where(
            TaskRun.scope_type == "document",
            TaskRun.scope_id == doc.id,
            TaskRun.task_name == "compute_intelligence",
        )
    )
    await session.commit()

    # Avoid an import-cycle by importing the worker module lazily here.
    from app.workers.intelligence import compute_intelligence_task

    compute_intelligence_task.delay(str(doc.id))
    return {"status": "accepted", "document_id": str(doc.id)}
