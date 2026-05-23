"""Credibility scoring Celery workers (Phase 2.5).

Two tasks:
  compute_credibility_task   – score a single document
  recompute_credibility_cohort_task – fan-out re-score for all neighbor docs
                                      after a document's claims change

The cohort task uses a Redis lock to prevent stampedes when many documents
in the same cohort all finish processing around the same time.
"""
from __future__ import annotations

import time
import uuid

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.metrics import (
    CREDIBILITY_COHORT_SIZE,
    CREDIBILITY_COMPUTE_DURATION,
    TASK_FAILURES,
)
from app.db.sync_session import get_sync_session
from app.services.credibility import compute_credibility, find_neighbor_documents
from app.workers.celery_app import celery_app
from app.workers.idempotency import idempotent_task

configure_logging()
log = get_logger(__name__)


@celery_app.task(
    name="compute_credibility",
    bind=True,
    queue="credibility",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=2,
)
def compute_credibility_task(self, document_id: str) -> str:
    session = get_sync_session()
    try:
        with idempotent_task(session, "document", document_id, "compute_credibility") as ctx:
            if ctx.skipped:
                return document_id

            doc_uuid = uuid.UUID(document_id)
            t0 = time.perf_counter()
            breakdown = compute_credibility(session, doc_uuid, _get_user_id(session, doc_uuid))
            CREDIBILITY_COMPUTE_DURATION.labels(kind="single").observe(time.perf_counter() - t0)

            log.info(
                "compute_credibility.done",
                document_id=document_id,
                score=breakdown.get("score"),
            )
        return document_id

    except Exception as e:
        session.rollback()
        TASK_FAILURES.labels(task="compute_credibility").inc()
        log.exception("compute_credibility.failed", document_id=document_id)
        try:
            import sentry_sdk
            sentry_sdk.capture_exception(e)
        except Exception:
            pass
        raise
    finally:
        session.close()


@celery_app.task(
    name="recompute_credibility_cohort",
    bind=True,
    queue="credibility",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=180,
    retry_jitter=True,
    max_retries=1,
)
def recompute_credibility_cohort_task(self, document_id: str) -> str:
    """Re-score neighbor documents whose credibility depends on this document."""
    settings = get_settings()
    session = get_sync_session()
    try:
        doc_uuid = uuid.UUID(document_id)
        user_id = _get_user_id(session, doc_uuid)

        neighbor_ids = find_neighbor_documents(
            session,
            document_id=doc_uuid,
            user_id=user_id,
            max_neighbors=settings.credibility_cohort_max_neighbors,
        )
        CREDIBILITY_COHORT_SIZE.observe(len(neighbor_ids))

        if not neighbor_ids:
            return document_id

        lock_key = f"credibility:cohort_lock:{document_id}"
        try:
            import redis as redis_lib
            r = redis_lib.from_url(settings.redis_url, decode_responses=True)
            acquired = r.set(
                lock_key, "1",
                nx=True,
                ex=settings.credibility_cohort_redis_lock_ttl_s,
            )
            if not acquired:
                log.info(
                    "recompute_credibility_cohort.skipped_lock",
                    document_id=document_id,
                )
                return document_id
        except Exception:
            pass  # proceed without lock if Redis is unavailable

        t0 = time.perf_counter()
        scored = 0
        for nbr_id in neighbor_ids:
            try:
                compute_credibility(session, nbr_id, user_id)
                scored += 1
            except Exception:
                log.warning(
                    "recompute_credibility_cohort.neighbor_failed",
                    neighbor_id=str(nbr_id),
                )

        CREDIBILITY_COMPUTE_DURATION.labels(kind="cohort").observe(time.perf_counter() - t0)
        log.info(
            "recompute_credibility_cohort.done",
            document_id=document_id,
            neighbors=len(neighbor_ids),
            scored=scored,
        )
        return document_id

    except Exception as e:
        session.rollback()
        TASK_FAILURES.labels(task="recompute_credibility_cohort").inc()
        log.exception("recompute_credibility_cohort.failed", document_id=document_id)
        try:
            import sentry_sdk
            sentry_sdk.capture_exception(e)
        except Exception:
            pass
        raise
    finally:
        session.close()


def _get_user_id(session, document_id: uuid.UUID) -> uuid.UUID:
    from app.models.document import Document
    doc = session.get(Document, document_id)
    if doc is None:
        raise RuntimeError(f"Document {document_id} not found")
    return doc.user_id
