"""Alert rules management API — Phase 4 Track G.

GET    /api/alerts/rules        — list user's alert rules
POST   /api/alerts/rules        — create a new alert rule
GET    /api/alerts/rules/{id}   — get a specific rule
PATCH  /api/alerts/rules/{id}   — update a rule
DELETE /api/alerts/rules/{id}   — delete a rule
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.exceptions import NotFoundError
from app.db.session import get_session
from app.models.alert import ALERT_TYPES, AlertRule
from app.models.user import User

router = APIRouter(prefix="/api", tags=["alerts"])


# ─── schemas ──────────────────────────────────────────────────────────────────

class AlertRuleCreate(BaseModel):
    name: str
    alert_type: str
    config: dict[str, Any] = {}
    enabled: bool = True

    @field_validator("alert_type")
    @classmethod
    def validate_alert_type(cls, v: str) -> str:
        if v not in ALERT_TYPES:
            raise ValueError(f"alert_type must be one of {ALERT_TYPES}")
        return v


class AlertRuleUpdate(BaseModel):
    name: str | None = None
    config: dict[str, Any] | None = None
    enabled: bool | None = None


class AlertRuleOut(BaseModel):
    id: uuid.UUID
    name: str
    alert_type: str
    config: dict[str, Any]
    enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}


def _serialize(rule: AlertRule) -> AlertRuleOut:
    return AlertRuleOut(
        id=rule.id,
        name=rule.name,
        alert_type=rule.alert_type,
        config=rule.config,
        enabled=rule.enabled,
        created_at=rule.created_at,
    )


# ─── endpoints ────────────────────────────────────────────────────────────────

@router.get("/alerts/rules", response_model=list[AlertRuleOut])
async def list_alert_rules(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[AlertRuleOut]:
    rules = (
        await session.execute(
            select(AlertRule)
            .where(AlertRule.user_id == current_user.id)
            .order_by(AlertRule.created_at.desc())
        )
    ).scalars().all()
    return [_serialize(r) for r in rules]


@router.post("/alerts/rules", response_model=AlertRuleOut, status_code=status.HTTP_201_CREATED)
async def create_alert_rule(
    body: AlertRuleCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AlertRuleOut:
    rule = AlertRule(
        user_id=current_user.id,
        name=body.name,
        alert_type=body.alert_type,
        config=body.config,
        enabled=body.enabled,
    )
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return _serialize(rule)


@router.get("/alerts/rules/{rule_id}", response_model=AlertRuleOut)
async def get_alert_rule(
    rule_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AlertRuleOut:
    rule = (
        await session.execute(
            select(AlertRule).where(
                AlertRule.id == rule_id,
                AlertRule.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if rule is None:
        raise NotFoundError("Alert rule not found")
    return _serialize(rule)


@router.patch("/alerts/rules/{rule_id}", response_model=AlertRuleOut)
async def update_alert_rule(
    rule_id: uuid.UUID,
    body: AlertRuleUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AlertRuleOut:
    rule = (
        await session.execute(
            select(AlertRule).where(
                AlertRule.id == rule_id,
                AlertRule.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if rule is None:
        raise NotFoundError("Alert rule not found")

    if body.name is not None:
        rule.name = body.name
    if body.config is not None:
        rule.config = body.config
    if body.enabled is not None:
        rule.enabled = body.enabled

    await session.commit()
    await session.refresh(rule)
    return _serialize(rule)


@router.delete("/alerts/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert_rule(
    rule_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    rule = (
        await session.execute(
            select(AlertRule).where(
                AlertRule.id == rule_id,
                AlertRule.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if rule is None:
        raise NotFoundError("Alert rule not found")

    await session.delete(rule)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
