"""Flashcard generation Celery worker (Phase 3.6).

Triggered on demand by POST /api/cards/generate. For each chunk in the
document, asks the local LLM for study cards and inserts them. Idempotent
per chunk via `task_runs` so re-running only processes new chunks.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select

from app.core.logging import configure_logging, get_logger
from app.core.metrics import TASK_FAILURES
from app.db.sync_session import get_sync_session
from app.models.chunk import Chunk
from app.models.flashcard import Flashcard
from app.services.cards import generate_cards_for_chunk
from app.workers.celery_app import celery_app
from app.workers.idempotency import idempotent_task

configure_logging()
log = get_logger(__name__)


@celery_app.task(
    name="generate_cards",
    bind=True,
    queue="cards",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=2,
)
def generate_cards_task(self, document_id: str) -> str:
    session = get_sync_session()
    try:
        doc_uuid = uuid.UUID(document_id)

        chunk_rows = session.execute(
            select(Chunk.id, Chunk.user_id, Chunk.text_content)
            .where(Chunk.document_id == doc_uuid)
            .order_by(Chunk.chunk_index)
        ).all()

        if not chunk_rows:
            log.info("generate_cards.no_chunks", document_id=document_id)
            return document_id

        total = 0
        for chunk_id, user_id, chunk_text in chunk_rows:
            with idempotent_task(session, "chunk", chunk_id, "generate_cards") as ctx:
                if ctx.skipped:
                    continue
                cards = generate_cards_for_chunk(chunk_text)
                for card in cards:
                    session.add(
                        Flashcard(
                            user_id=user_id,
                            chunk_id=chunk_id,
                            document_id=doc_uuid,
                            question=card["question"],
                            answer=card["answer"],
                        )
                    )
                session.commit()
                total += len(cards)

        log.info(
            "generate_cards.done",
            document_id=document_id,
            chunks=len(chunk_rows),
            cards=total,
        )
        return document_id

    except Exception as e:
        session.rollback()
        TASK_FAILURES.labels(task="generate_cards").inc()
        log.exception("generate_cards.failed", document_id=document_id)
        try:
            import sentry_sdk

            sentry_sdk.capture_exception(e)
        except Exception:
            pass
        raise
    finally:
        session.close()
