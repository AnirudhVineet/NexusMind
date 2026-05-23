"""Credibility scoring API (Phase 2.5).

GET  /api/documents/{id}/credibility   – current score + breakdown
POST /api/documents/{id}/credibility   – trigger recompute
GET  /api/credibility/weights          – current weight set
PUT  /api/credibility/weights          – update weights in Redis
"""
from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.exceptions import NotFoundError
from app.db.session import get_session
from app.models.document import Document
from app.models.user import User
from app.schemas.credibility import CredibilityResponse, CredibilityWeights
from app.services.credibility import get_weights, score_label

router = APIRouter(prefix="/api", tags=["credibility"])

_WEIGHTS_REDIS_KEY = "credibility:weights:current"
_WEIGHTS_VERSION_KEY = "credibility:weights:version"


async def _get_doc(
    document_id: uuid.UUID,
    user: User,
    session: AsyncSession,
) -> Document:
    doc = (
        await session.execute(
            select(Document).where(
                Document.id == document_id, Document.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        raise NotFoundError("Document not found")
    return doc


@router.get(
    "/documents/{document_id}/credibility",
    response_model=CredibilityResponse,
)
async def get_credibility(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CredibilityResponse:
    doc = await _get_doc(document_id, current_user, session)
    return CredibilityResponse(
        document_id=doc.id,
        score=doc.credibility_score,
        label=score_label(doc.credibility_score) if doc.credibility_score is not None else None,
        breakdown=doc.credibility_breakdown,
        computed_at=doc.credibility_computed_at,
    )


@router.post(
    "/documents/{document_id}/credibility",
    response_model=CredibilityResponse,
    status_code=202,
)
async def trigger_credibility_recompute(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CredibilityResponse:
    """Enqueue an immediate credibility recompute for this document."""
    doc = await _get_doc(document_id, current_user, session)

    from app.workers.credibility import compute_credibility_task
    compute_credibility_task.apply_async(args=[str(document_id)])

    return CredibilityResponse(
        document_id=doc.id,
        score=doc.credibility_score,
        label=score_label(doc.credibility_score) if doc.credibility_score is not None else None,
        breakdown=doc.credibility_breakdown,
        computed_at=doc.credibility_computed_at,
    )


@router.get("/credibility/weights", response_model=CredibilityWeights)
async def get_credibility_weights(
    current_user: User = Depends(get_current_user),
) -> CredibilityWeights:
    weights, _ = get_weights()
    return CredibilityWeights(**weights)


@router.put("/credibility/weights", response_model=CredibilityWeights)
async def update_credibility_weights(
    body: CredibilityWeights,
    current_user: User = Depends(get_current_user),
) -> CredibilityWeights:
    weights_dict = body.model_dump()
    total = sum(weights_dict.values())
    if abs(total - 1.0) > 0.01:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail=f"Weights must sum to 1.0 (got {total:.4f})")

    try:
        import redis as redis_lib
        from app.core.config import get_settings
        import time
        s = get_settings()
        r = redis_lib.from_url(s.redis_url, decode_responses=True)
        r.set(_WEIGHTS_REDIS_KEY, json.dumps(weights_dict))
        r.set(_WEIGHTS_VERSION_KEY, str(int(time.time())))
    except Exception as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=f"Redis unavailable: {exc}")

    return body
