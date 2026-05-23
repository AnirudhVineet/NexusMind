"""Automation Workflows API — Phase 4 Track F.

CRUD for workflows and workflow runs, plus a /test endpoint.

GET    /api/workflows              — list workflows
POST   /api/workflows              — create workflow
GET    /api/workflows/{id}         — get workflow
PATCH  /api/workflows/{id}         — update workflow
DELETE /api/workflows/{id}         — delete workflow (204)
POST   /api/workflows/{id}/test    — fire synthetic event and return match result
GET    /api/workflows/{id}/runs    — list recent runs
"""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import get_session
from app.models.user import User
from app.models.workflow import ACTION_TYPES, TRIGGER_EVENTS, Workflow, WorkflowRun

router = APIRouter(prefix="/api", tags=["workflows"])


# ─── Pydantic schemas ──────────────────────────────────────────────────────────


class WorkflowCreate(BaseModel):
    name: str
    trigger_event: str
    conditions: dict[str, Any] = {}
    action_type: str
    action_config: dict[str, Any] = {}
    enabled: bool = True


class WorkflowUpdate(BaseModel):
    name: str | None = None
    trigger_event: str | None = None
    conditions: dict[str, Any] | None = None
    action_type: str | None = None
    action_config: dict[str, Any] | None = None
    enabled: bool | None = None


class WorkflowOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    trigger_event: str
    conditions: dict[str, Any]
    action_type: str
    action_config: dict[str, Any]
    enabled: bool
    created_at: datetime
    last_run_at: datetime | None
    run_count: int


class RunOut(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    status: str
    started_at: datetime
    completed_at: datetime | None
    error_message: str | None


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _mask_webhook_secret(config: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of action_config with webhook_secret masked."""
    if "webhook_secret" in config:
        config = {**config, "webhook_secret": "***"}
    return config


def _workflow_out(wf: Workflow, *, reveal_secret: bool = False) -> WorkflowOut:
    config = wf.action_config or {}
    if not reveal_secret and wf.action_type == "fire_webhook":
        config = _mask_webhook_secret(config)
    return WorkflowOut(
        id=wf.id,
        user_id=wf.user_id,
        name=wf.name,
        trigger_event=wf.trigger_event,
        conditions=wf.conditions or {},
        action_type=wf.action_type,
        action_config=config,
        enabled=wf.enabled,
        created_at=wf.created_at,
        last_run_at=wf.last_run_at,
        run_count=wf.run_count,
    )


async def _get_owned_workflow(
    workflow_id: uuid.UUID,
    user: User,
    session: AsyncSession,
) -> Workflow:
    wf = (
        await session.execute(
            select(Workflow).where(
                Workflow.id == workflow_id,
                Workflow.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if wf is None:
        raise NotFoundError("Workflow not found")
    return wf


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/workflows", response_model=list[WorkflowOut])
async def list_workflows(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[WorkflowOut]:
    rows = (
        await session.execute(
            select(Workflow)
            .where(Workflow.user_id == current_user.id)
            .order_by(Workflow.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [_workflow_out(wf) for wf in rows]


@router.post("/workflows", status_code=status.HTTP_201_CREATED, response_model=WorkflowOut)
async def create_workflow(
    body: WorkflowCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> WorkflowOut:
    if body.trigger_event not in TRIGGER_EVENTS:
        raise ValidationError(
            f"Invalid trigger_event. Must be one of: {TRIGGER_EVENTS}"
        )
    if body.action_type not in ACTION_TYPES:
        raise ValidationError(
            f"Invalid action_type. Must be one of: {ACTION_TYPES}"
        )

    config = dict(body.action_config)
    # Auto-generate webhook_secret for fire_webhook actions
    if body.action_type == "fire_webhook" and "webhook_secret" not in config:
        config["webhook_secret"] = secrets.token_hex(32)

    wf = Workflow(
        user_id=current_user.id,
        name=body.name,
        trigger_event=body.trigger_event,
        conditions=body.conditions,
        action_type=body.action_type,
        action_config=config,
        enabled=body.enabled,
    )
    session.add(wf)
    await session.commit()
    await session.refresh(wf)
    # Reveal secret on creation response so the user can copy it
    return _workflow_out(wf, reveal_secret=True)


@router.get("/workflows/{workflow_id}", response_model=WorkflowOut)
async def get_workflow(
    workflow_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> WorkflowOut:
    wf = await _get_owned_workflow(workflow_id, current_user, session)
    return _workflow_out(wf)


@router.patch("/workflows/{workflow_id}", response_model=WorkflowOut)
async def update_workflow(
    workflow_id: uuid.UUID,
    body: WorkflowUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> WorkflowOut:
    wf = await _get_owned_workflow(workflow_id, current_user, session)

    if body.name is not None:
        wf.name = body.name
    if body.trigger_event is not None:
        if body.trigger_event not in TRIGGER_EVENTS:
            raise ValidationError(
                f"Invalid trigger_event. Must be one of: {TRIGGER_EVENTS}"
            )
        wf.trigger_event = body.trigger_event
    if body.conditions is not None:
        wf.conditions = body.conditions
    if body.action_type is not None:
        if body.action_type not in ACTION_TYPES:
            raise ValidationError(
                f"Invalid action_type. Must be one of: {ACTION_TYPES}"
            )
        wf.action_type = body.action_type
    if body.action_config is not None:
        wf.action_config = body.action_config
    if body.enabled is not None:
        wf.enabled = body.enabled

    await session.commit()
    await session.refresh(wf)
    return _workflow_out(wf)


@router.delete(
    "/workflows/{workflow_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_workflow(
    workflow_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    wf = await _get_owned_workflow(workflow_id, current_user, session)
    await session.delete(wf)
    await session.commit()


@router.post("/workflows/{workflow_id}/test")
async def test_workflow(
    workflow_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Fire a synthetic event payload and return whether the workflow would match."""
    from app.services.workflows import _check_conditions

    wf = await _get_owned_workflow(workflow_id, current_user, session)

    # Build a synthetic payload that satisfies all known condition types
    synthetic_payload: dict[str, Any] = {
        "topic": "test",
        "tags": ["test"],
        "confidence": 1.0,
        "source_type": "web",
        "_synthetic": True,
    }

    matched = _check_conditions(wf.conditions or {}, synthetic_payload)
    return {"status": "ok", "matched": matched}


@router.get("/workflows/{workflow_id}/runs", response_model=list[RunOut])
async def list_workflow_runs(
    workflow_id: uuid.UUID,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[RunOut]:
    # Verify ownership
    await _get_owned_workflow(workflow_id, current_user, session)

    runs = (
        await session.execute(
            select(WorkflowRun)
            .where(WorkflowRun.workflow_id == workflow_id)
            .order_by(WorkflowRun.started_at.desc())
            .limit(limit)
        )
    ).scalars().all()

    return [
        RunOut(
            id=r.id,
            workflow_id=r.workflow_id,
            status=r.status,
            started_at=r.started_at,
            completed_at=r.completed_at,
            error_message=r.error_message,
        )
        for r in runs
    ]
