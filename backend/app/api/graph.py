"""Knowledge graph API endpoints."""
from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.graph import (
    EdgeDetail,
    EntityDetail,
    GraphPayload,
)
from app.services import graph as graph_svc

router = APIRouter(prefix="/api", tags=["graph"])


@router.get("/graph", response_model=GraphPayload)
async def get_graph(
    entity_id: Optional[uuid.UUID] = Query(default=None),
    document_id: Optional[uuid.UUID] = Query(default=None),
    depth: int = Query(default=1, ge=1, le=3),
    min_confidence: float = Query(default=0.7, ge=0.0, le=1.0),
    types: Optional[List[str]] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GraphPayload:
    if entity_id is None:
        nodes, edges = await graph_svc.initial_graph(
            session,
            user_id=user.id,
            document_id=document_id,
            types=types,
            min_confidence=min_confidence,
            limit=limit,
        )
    else:
        nodes, edges = await graph_svc.neighborhood(
            session,
            user_id=user.id,
            entity_id=entity_id,
            depth=depth,
            min_confidence=min_confidence,
            types=types,
            limit=limit,
        )
    return GraphPayload.model_validate({"nodes": nodes, "edges": edges})


@router.get("/graph/expand", response_model=GraphPayload)
async def expand_graph(
    entity_id: uuid.UUID = Query(...),
    depth: int = Query(default=2, ge=1, le=3),
    min_confidence: float = Query(default=0.7, ge=0.0, le=1.0),
    limit: int = Query(default=200, ge=1, le=1000),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GraphPayload:
    nodes, edges = await graph_svc.neighborhood(
        session,
        user_id=user.id,
        entity_id=entity_id,
        depth=depth,
        min_confidence=min_confidence,
        limit=limit,
    )
    return GraphPayload.model_validate({"nodes": nodes, "edges": edges})


@router.get("/entities/{entity_id}", response_model=EntityDetail)
async def get_entity(
    entity_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> EntityDetail:
    payload = await graph_svc.entity_detail(
        session, user_id=user.id, entity_id=entity_id
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="entity not found")
    return EntityDetail.model_validate(payload)


@router.get("/edges/{edge_id}", response_model=EdgeDetail)
async def get_edge(
    edge_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> EdgeDetail:
    payload = await graph_svc.edge_detail(session, user_id=user.id, edge_id=edge_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="edge not found")
    return EdgeDetail.model_validate(payload)
