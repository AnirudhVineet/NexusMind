"""Document intelligence Celery worker.

Runs `compute_for_document` then writes results back to:
- `documents.intelligence` (JSONB blob)
- `topic_tags` / `document_tags` (so tags are queryable as first-class filters)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.logging import configure_logging, get_logger
from app.core.metrics import TASK_FAILURES
from app.db.sync_session import get_sync_session
from app.models.document import Document
from app.models.topic import DocumentTag, TopicTag
from app.services.intelligence import compute_for_document
from app.workers.celery_app import celery_app
from app.workers.idempotency import idempotent_task

configure_logging()
log = get_logger(__name__)


def _upsert_tags(session, *, user_id: uuid.UUID, document_id: uuid.UUID, tag_payloads: list[dict]) -> None:
    """Insert or look up TopicTag rows and link them via DocumentTag."""
    # Replace this document's tag set wholesale so re-runs don't leave stale rows.
    session.execute(delete(DocumentTag).where(DocumentTag.document_id == document_id))

    for tag in tag_payloads:
        slug = tag["slug"]
        display_name = tag.get("display_name") or slug
        confidence = float(tag.get("confidence", 0))

        tag_row = session.execute(
            select(TopicTag).where(
                TopicTag.user_id == user_id, TopicTag.slug == slug
            )
        ).scalar_one_or_none()
        if tag_row is None:
            tag_id = uuid.uuid4()
            session.execute(
                TopicTag.__table__.insert().values(
                    id=tag_id,
                    user_id=user_id,
                    slug=slug,
                    display_name=display_name,
                    source="llm",
                )
            )
        else:
            tag_id = tag_row.id

        session.execute(
            pg_insert(DocumentTag)
            .values(
                document_id=document_id,
                tag_id=tag_id,
                confidence=confidence,
            )
            .on_conflict_do_update(
                index_elements=["document_id", "tag_id"],
                set_={"confidence": confidence},
            )
        )


@celery_app.task(
    name="compute_intelligence",
    bind=True,
    queue="intelligence",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=2,
)
def compute_intelligence_task(self, document_id: str) -> str:
    session = get_sync_session()
    try:
        with idempotent_task(
            session, "document", document_id, "compute_intelligence"
        ) as ctx:
            if ctx.skipped:
                return document_id

            doc_uuid = uuid.UUID(document_id)
            doc = session.get(Document, doc_uuid)
            if doc is None:
                raise RuntimeError(f"Document {document_id} not found")

            payload = compute_for_document(session, doc_uuid)

            tag_payloads = payload.pop("tags", []) or []
            # Preserve the slug list inside the JSONB blob for the UI badge tooltip
            # without forcing a join.
            payload["tags"] = [t["slug"] for t in tag_payloads]

            doc.intelligence = payload
            doc.intelligence_computed_at = datetime.now(timezone.utc)
            session.commit()

            _upsert_tags(
                session,
                user_id=doc.user_id,
                document_id=doc.id,
                tag_payloads=tag_payloads,
            )
            session.commit()

            log.info(
                "compute_intelligence.done",
                document_id=document_id,
                tag_count=len(tag_payloads),
                insight_count=len(payload.get("key_insights") or []),
            )
        return document_id

    except Exception as e:
        session.rollback()
        TASK_FAILURES.labels(task="compute_intelligence").inc()
        log.exception("compute_intelligence.failed", document_id=document_id)
        try:
            import sentry_sdk

            sentry_sdk.capture_exception(e)
        except Exception:
            pass
        raise
    finally:
        session.close()
