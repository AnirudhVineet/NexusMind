"""Research brief generation Celery worker — Phase 4 Track B.

Runs the full research pipeline:
  1. Expand topic into sub-queries (Groq/Ollama)
  2. Gather evidence chunks via hybrid search
  3. Synthesize a structured ResearchBrief (Groq/Ollama)
  4. Persist the result to the research_briefs row

Uses a FRESH AsyncSession per DB transaction (not one shared across the
whole pipeline) — otherwise LLM/embedding calls between DB ops trigger
"This session is provisioning a new connection; concurrent operations
are not permitted" errors.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.logging import configure_logging, get_logger
from app.models.research_brief import ResearchBrief as ResearchBriefModel
from app.workers._async_utils import run_async_task
from app.workers.celery_app import celery_app

configure_logging()
log = get_logger(__name__)


async def _set_status(bid: uuid.UUID, **fields) -> None:
    """Update the brief row in its own short-lived transaction."""
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        row = (
            await session.execute(
                select(ResearchBriefModel).where(ResearchBriefModel.id == bid)
            )
        ).scalar_one_or_none()
        if row is None:
            return
        for k, v in fields.items():
            setattr(row, k, v)
        await session.commit()


async def _load_brief(bid: uuid.UUID) -> tuple[str, uuid.UUID] | None:
    """Return (topic, user_id) for the brief, or None if missing."""
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        row = (
            await session.execute(
                select(ResearchBriefModel.topic, ResearchBriefModel.user_id).where(
                    ResearchBriefModel.id == bid
                )
            )
        ).first()
        if row is None:
            return None
        return row[0], row[1]


async def _run_brief(brief_id: str) -> None:
    from app.db.session import AsyncSessionLocal
    from app.services.research import (
        NoEvidenceError,
        expand_query,
        gather_evidence,
        synthesize_brief,
    )

    bid = uuid.UUID(brief_id)

    loaded = await _load_brief(bid)
    if loaded is None:
        log.error("research_brief.not_found", brief_id=brief_id)
        return
    topic, user_id = loaded

    try:
        # Stage 1: retrieving
        await _set_status(bid, status="retrieving")

        sub_queries = await expand_query(topic)
        log.info(
            "research_brief.sub_queries",
            brief_id=brief_id,
            count=len(sub_queries),
        )

        # Use a fresh session for evidence gathering
        async with AsyncSessionLocal() as gather_session:
            chunks = await gather_evidence(sub_queries, user_id, gather_session)
        log.info(
            "research_brief.evidence_gathered",
            brief_id=brief_id,
            chunks=len(chunks),
        )

        # Stage 2: synthesizing
        await _set_status(bid, status="synthesizing")

        brief = await synthesize_brief(topic, chunks)
        brief_dict = brief.model_dump()

        # Stage 3: complete
        await _set_status(
            bid,
            status="complete",
            brief_json=brief_dict,
            completed_at=datetime.now(timezone.utc),
        )

        log.info("research_brief.complete", brief_id=brief_id)

    except NoEvidenceError as exc:
        # Library has nothing relevant — user-facing failure, no retry.
        log.info(
            "research_brief.no_evidence", brief_id=brief_id, msg=str(exc)
        )
        try:
            await _set_status(
                bid,
                status="failed",
                error_message=str(exc),
                completed_at=datetime.now(timezone.utc),
            )
        except Exception:
            log.exception(
                "research_brief.status_update_failed", brief_id=brief_id
            )
        return
    except Exception as exc:
        log.exception("research_brief.failed", brief_id=brief_id)
        try:
            await _set_status(
                bid, status="failed", error_message=str(exc)[:2000]
            )
        except Exception:
            log.exception(
                "research_brief.status_update_failed", brief_id=brief_id
            )
        try:
            import sentry_sdk

            sentry_sdk.capture_exception(exc)
        except Exception:
            pass
        raise


@celery_app.task(
    name="generate_research_brief",
    bind=True,
    queue="research",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=2,
)
def generate_research_brief_task(self, brief_id: str) -> str:
    # `run_async_task` disposes the async DB engine after the run, so the
    # next research brief task starts with a fresh asyncpg pool. Without
    # this, the second brief would hang at status="queued" forever — see
    # `app.workers._async_utils.run_async_task`.
    run_async_task(_run_brief(brief_id))
    return brief_id
