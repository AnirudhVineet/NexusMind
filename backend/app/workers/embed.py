import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.logging import configure_logging, get_logger
from app.db.sync_session import get_sync_session
from app.models.chunk import Chunk
from app.models.document import Document
from app.services.embedding import embed_batch_sync
from app.workers.celery_app import celery_app

configure_logging()
log = get_logger(__name__)

BATCH_SIZE = 100


@celery_app.task(
    name="embed_chunks",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=3,
)
def embed_chunks(self, document_id: str) -> str:
    session = get_sync_session()

    try:
        doc = session.get(Document, uuid.UUID(document_id))
        if doc is None:
            raise RuntimeError(f"Document {document_id} not found")

        # Pull all chunks needing embeddings
        rows = list(
            session.execute(
                select(Chunk)
                .where(Chunk.document_id == doc.id)
                .where(Chunk.embedding.is_(None))
                .order_by(Chunk.chunk_index)
            ).scalars()
        )

        total_chunks = doc.chunk_count or 0

        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i : i + BATCH_SIZE]
            texts = [c.text_content for c in batch]
            vectors = embed_batch_sync(texts)

            for chunk_row, vec in zip(batch, vectors):
                chunk_row.embedding = vec
            session.commit()

            if total_chunks > 500 and i + BATCH_SIZE < len(rows):
                time.sleep(1)

        doc.processing_status = "complete"
        doc.completed_at = datetime.now(timezone.utc)
        session.commit()

        return document_id

    except Exception as e:
        session.rollback()
        log.exception("embed_chunks.failed", document_id=document_id)
        try:
            doc = session.get(Document, uuid.UUID(document_id))
            if doc:
                doc.processing_status = "failed"
                doc.error_message = str(e)[:2000]
                session.commit()
        except Exception:
            session.rollback()
        try:
            import sentry_sdk

            sentry_sdk.capture_exception(e)
        except Exception:
            pass
        raise
    finally:
        session.close()
