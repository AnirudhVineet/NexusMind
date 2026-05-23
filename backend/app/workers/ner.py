"""NER Celery worker — extract entities for every chunk in a document.

This task runs *after* embed_chunks completes for a document. It is split
into a single document-scoped task (rather than one task per chunk) so that
spaCy / GLiNER / MiniLM are loaded once and amortised across the whole doc.

Idempotent at the chunk level: every (chunk, 'extract_entities') pair has a
row in `task_runs`. Re-running on a partially-processed document picks up
only the chunks that didn't reach 'success'.
"""
from __future__ import annotations

import time
import uuid

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.logging import configure_logging, get_logger
from app.core.metrics import NER_DURATION, TASK_FAILURES
from app.db.sync_session import get_sync_session
from app.models.chunk import Chunk
from app.models.entity import ChunkEntity
from app.services.entity_dedup import upsert_entity
from app.services.entity_embedding import embed_batch
from app.services.ner import ExtractedEntity, extract_entities
from app.workers.celery_app import celery_app
from app.workers.idempotency import idempotent_task

configure_logging()
log = get_logger(__name__)


def _process_chunk(session, chunk: Chunk) -> int:
    """Run NER on one chunk, upsert entities, record chunk_entities.

    Returns the number of (entity, span) links written for this chunk.
    """
    text = chunk.text_content
    if not text or not text.strip():
        return 0

    t0 = time.perf_counter()
    extracted: list[ExtractedEntity] = extract_entities(text)
    NER_DURATION.labels(extractor="spacy_gliner").observe(time.perf_counter() - t0)

    if not extracted:
        return 0

    # Batch-embed all extracted names so we hit MiniLM once per chunk.
    embeddings = embed_batch([e.name for e in extracted])

    # Replace any existing chunk_entities for this chunk so re-runs are clean.
    session.execute(delete(ChunkEntity).where(ChunkEntity.chunk_id == chunk.id))

    written = 0
    for ent, vec in zip(extracted, embeddings):
        result = upsert_entity(
            session,
            user_id=chunk.user_id,
            surface_form=ent.name,
            entity_type=ent.type,
            embedding=vec,
        )
        session.execute(
            pg_insert(ChunkEntity)
            .values(
                chunk_id=chunk.id,
                entity_id=result.entity_id,
                char_start=ent.char_start,
                char_end=ent.char_end,
            )
            .on_conflict_do_nothing(constraint="pk_chunk_entities")
        )
        written += 1

    return written


@celery_app.task(
    name="extract_entities",
    bind=True,
    queue="ner",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=3,
)
def extract_entities_task(self, document_id: str) -> str:
    session = get_sync_session()
    try:
        chunk_ids = [
            row[0]
            for row in session.execute(
                select(Chunk.id)
                .where(Chunk.document_id == uuid.UUID(document_id))
                .order_by(Chunk.chunk_index)
            ).all()
        ]

        if not chunk_ids:
            log.info("extract_entities.no_chunks", document_id=document_id)
            return document_id

        total_links = 0
        for cid in chunk_ids:
            with idempotent_task(session, "chunk", cid, "extract_entities") as ctx:
                if ctx.skipped:
                    continue
                chunk = session.get(Chunk, cid)
                if chunk is None:
                    continue
                links = _process_chunk(session, chunk)
                session.commit()
                total_links += links

        log.info(
            "extract_entities.done",
            document_id=document_id,
            chunks=len(chunk_ids),
            entity_links=total_links,
        )
        return document_id

    except Exception as e:
        session.rollback()
        TASK_FAILURES.labels(task="extract_entities").inc()
        log.exception("extract_entities.failed", document_id=document_id)
        try:
            import sentry_sdk

            sentry_sdk.capture_exception(e)
        except Exception:
            pass
        raise
    finally:
        session.close()
