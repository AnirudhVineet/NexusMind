import asyncio
import json
import uuid

from sqlalchemy import delete

from app.core.logging import configure_logging, get_logger
from app.db.sync_session import get_sync_session
from app.models.chunk import Chunk
from app.models.document import Document
from app.services.chunking import split_into_chunks
from app.services.storage import StorageService
from app.workers.celery_app import celery_app

configure_logging()
log = get_logger(__name__)


@celery_app.task(
    name="chunk_document",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
)
def chunk_document(self, document_id: str) -> str:
    storage = StorageService()
    session = get_sync_session()

    try:
        doc = session.get(Document, uuid.UUID(document_id))
        if doc is None:
            raise RuntimeError(f"Document {document_id} not found")

        parsed_key = f"{doc.user_id}/{doc.id}/parsed.json"
        raw = asyncio.run(storage.download(parsed_key))
        parsed = json.loads(raw.decode("utf-8"))
        pages = parsed["pages"]

        chunks = split_into_chunks(pages, chunk_size=500, chunk_overlap=50)

        # idempotency: clear any existing chunks
        session.execute(delete(Chunk).where(Chunk.document_id == doc.id))

        rows = [
            Chunk(
                document_id=doc.id,
                user_id=doc.user_id,
                chunk_index=c.chunk_index,
                text_content=c.text,
                page_number=c.page_number,
                section=None,
                char_offset=c.char_offset,
                token_count=c.token_count,
                embedding=None,
            )
            for c in chunks
        ]
        if rows:
            session.add_all(rows)

        doc.chunk_count = len(rows)
        doc.processing_status = "embedding"
        session.commit()

        return document_id

    except Exception as e:
        session.rollback()
        log.exception("chunk_document.failed", document_id=document_id)
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
