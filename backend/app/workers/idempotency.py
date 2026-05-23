"""Idempotency wrapper for Celery tasks backed by `task_runs`.

Usage:

    with idempotent_task(session, "chunk", chunk_id, "extract_entities") as ctx:
        if ctx.skipped:
            return
        # ... do the work ...
        # Exiting the block successfully marks the row 'success'.
        # An exception marks 'failed' with the error message.
"""
from __future__ import annotations

import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterator, Literal

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.task_run import TaskRun


ScopeType = Literal["chunk", "document"]


@dataclass
class IdempotencyContext:
    skipped: bool


@contextmanager
def idempotent_task(
    session: Session,
    scope_type: ScopeType,
    scope_id: uuid.UUID | str,
    task_name: str,
) -> Iterator[IdempotencyContext]:
    if isinstance(scope_id, str):
        scope_id = uuid.UUID(scope_id)

    existing = session.execute(
        select(TaskRun).where(
            TaskRun.scope_type == scope_type,
            TaskRun.scope_id == scope_id,
            TaskRun.task_name == task_name,
        )
    ).scalar_one_or_none()

    if existing is not None and existing.status == "success":
        yield IdempotencyContext(skipped=True)
        return

    # Upsert started row. ON CONFLICT preserves the original row; we then
    # update its fields so a previously-failed run can be re-attempted.
    stmt = pg_insert(TaskRun).values(
        scope_type=scope_type,
        scope_id=scope_id,
        task_name=task_name,
        status="started",
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["scope_type", "scope_id", "task_name"],
        set_={
            "status": "started",
            "started_at": text("now()"),
            "ended_at": None,
            "error": None,
        },
    )
    session.execute(stmt)
    session.commit()

    try:
        yield IdempotencyContext(skipped=False)
    except Exception as e:
        session.rollback()
        session.execute(
            pg_insert(TaskRun)
            .values(
                scope_type=scope_type,
                scope_id=scope_id,
                task_name=task_name,
                status="failed",
                ended_at=datetime.now(timezone.utc),
                error=str(e)[:4000],
            )
            .on_conflict_do_update(
                index_elements=["scope_type", "scope_id", "task_name"],
                set_={
                    "status": "failed",
                    "ended_at": datetime.now(timezone.utc),
                    "error": str(e)[:4000],
                },
            )
        )
        session.commit()
        raise
    else:
        session.execute(
            pg_insert(TaskRun)
            .values(
                scope_type=scope_type,
                scope_id=scope_id,
                task_name=task_name,
                status="success",
                ended_at=datetime.now(timezone.utc),
            )
            .on_conflict_do_update(
                index_elements=["scope_type", "scope_id", "task_name"],
                set_={
                    "status": "success",
                    "ended_at": datetime.now(timezone.utc),
                    "error": None,
                },
            )
        )
        session.commit()
