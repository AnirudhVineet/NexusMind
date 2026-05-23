"""Annotation graph-projection worker (Phase 3.5).

Runs after an annotation is created or its note is edited. Embeds the
annotation text with all-MiniLM and, when the annotation carries a note
body, creates a `user_insight` entity linked to the source chunk's
entities so user-contributed knowledge is first-class in the graph.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.logging import configure_logging, get_logger
from app.core.metrics import TASK_FAILURES
from app.db.sync_session import get_sync_session
from app.models.annotation import Annotation
from app.models.entity import ChunkEntity, Entity
from app.models.entity_edge import EntityEdge
from app.services.entity_embedding import embed_one
from app.workers.celery_app import celery_app

configure_logging()
log = get_logger(__name__)


@celery_app.task(
    name="project_annotation",
    bind=True,
    queue="default",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=2,
)
def project_annotation_task(self, annotation_id: str) -> str:
    """Embed the annotation and, if it has a note, project it into the graph."""
    session = get_sync_session()
    try:
        ann = session.get(Annotation, uuid.UUID(annotation_id))
        if ann is None:
            log.info("project_annotation.missing", annotation_id=annotation_id)
            return annotation_id

        note = (ann.note or "").strip()
        embed_text = f"{note}\n\n{ann.highlight_text}".strip() if note else ann.highlight_text
        ann.embedding = embed_one(embed_text)

        if note:
            insight_name = note[:120]
            entity = Entity(
                user_id=ann.user_id,
                name=insight_name,
                canonical_name=insight_name.lower(),
                type="user_insight",
                embedding=ann.embedding,
                evidence_count=1,
            )
            session.add(entity)
            session.flush()
            ann.insight_entity_id = entity.id

            if ann.chunk_id is not None:
                neighbor_ids = (
                    session.execute(
                        select(ChunkEntity.entity_id).where(
                            ChunkEntity.chunk_id == ann.chunk_id
                        )
                    )
                    .scalars()
                    .all()
                )
                for dst_id in neighbor_ids:
                    session.execute(
                        pg_insert(EntityEdge)
                        .values(
                            user_id=ann.user_id,
                            src_id=entity.id,
                            dst_id=dst_id,
                            relation_type="relates_to",
                            confidence=1.0,
                            evidence_chunk_id=ann.chunk_id,
                            justification="Linked from user annotation",
                        )
                        .on_conflict_do_nothing()
                    )

        session.commit()
        log.info(
            "project_annotation.done",
            annotation_id=annotation_id,
            has_note=bool(note),
            insight_entity_id=str(ann.insight_entity_id) if ann.insight_entity_id else None,
        )
        return annotation_id

    except Exception as e:
        session.rollback()
        TASK_FAILURES.labels(task="project_annotation").inc()
        log.exception("project_annotation.failed", annotation_id=annotation_id)
        try:
            import sentry_sdk

            sentry_sdk.capture_exception(e)
        except Exception:
            pass
        raise
    finally:
        session.close()
