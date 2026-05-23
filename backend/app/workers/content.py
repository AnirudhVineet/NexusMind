"""Content repurposing Celery worker — Track H.

Loads a GeneratedContent row, fetches the relevant source chunks from the DB,
dispatches to the appropriate async generator function, and persists results.
"""
from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import select

from app.core.logging import configure_logging, get_logger
from app.core.metrics import TASK_FAILURES
from app.db.sync_session import get_sync_session
from app.models.chunk import Chunk
from app.models.generated_content import GeneratedContent
from app.workers.celery_app import celery_app

configure_logging()
log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Helpers to load source chunks
# ---------------------------------------------------------------------------

def _load_chunks_for_source(
    session,
    source_type: str,
    source_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[dict]:
    """Query source chunks based on source_type and source_id.

    Returns a list of dicts with id, text_content, and embedding keys
    so they can be safely serialised to JSON and passed to async generators.
    """
    if source_type == "chunk":
        # Single chunk
        rows = session.execute(
            select(Chunk).where(
                Chunk.id == source_id,
                Chunk.user_id == user_id,
            )
        ).scalars().all()

    elif source_type == "document":
        rows = session.execute(
            select(Chunk)
            .where(
                Chunk.document_id == source_id,
                Chunk.user_id == user_id,
            )
            .order_by(Chunk.chunk_index)
        ).scalars().all()

    elif source_type == "topic":
        # Chunks tagged with the given topic UUID via DocumentTag → document → chunk
        # DocumentTag schema: (document_id, tag_id, confidence). No user_id column —
        # we scope by Chunk.user_id instead.
        from app.models.topic import DocumentTag

        doc_ids = session.execute(
            select(DocumentTag.document_id).where(
                DocumentTag.tag_id == source_id,
            )
        ).scalars().all()

        if not doc_ids:
            return []

        rows = session.execute(
            select(Chunk)
            .where(
                Chunk.document_id.in_(doc_ids),
                Chunk.user_id == user_id,
            )
            .order_by(Chunk.chunk_index)
            .limit(30)
        ).scalars().all()

    elif source_type == "entity":
        # Chunks linked to the given entity via ChunkEntity
        from app.models.entity import ChunkEntity

        chunk_ids = session.execute(
            select(ChunkEntity.chunk_id).where(
                ChunkEntity.entity_id == source_id,
            )
        ).scalars().all()

        if not chunk_ids:
            return []

        rows = session.execute(
            select(Chunk)
            .where(
                Chunk.id.in_(chunk_ids),
                Chunk.user_id == user_id,
            )
            .order_by(Chunk.chunk_index)
            .limit(30)
        ).scalars().all()

    else:
        return []

    return [
        {
            "id": str(c.id),
            "text_content": c.text_content,
            # pgvector returns a numpy float32 array — convert each element
            # to a native Python float so the dict is JSON-serialisable.
            "embedding": [float(x) for x in c.embedding] if c.embedding is not None else [],
        }
        for c in rows
    ]


# ---------------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------------

@celery_app.task(
    name="generate_content",
    bind=True,
    # Dedicated `content` queue (served by the NM-content worker) so script /
    # caption / thread / meme generation doesn't sit behind the document
    # ingestion pipeline on the shared `intelligence` queue.
    queue="content",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=3,
)
def generate_content_task(
    self,
    content_id: str,
    strict_mode: bool = False,
    platform: str | None = None,
    length: str = "short",
) -> str:
    """Main worker entry-point for content generation.

    Loads the GeneratedContent row, fetches source chunks, calls the
    appropriate async generator, and persists the result.
    """
    session = get_sync_session()
    try:
        row_id = uuid.UUID(content_id)
        row: GeneratedContent | None = session.get(GeneratedContent, row_id)
        if row is None:
            log.warning("generate_content.row_not_found", content_id=content_id)
            return content_id

        # Mark as running
        row.status = "running"
        session.commit()

        source_chunks = _load_chunks_for_source(
            session, row.source_type, row.source_id, row.user_id
        )

        if not source_chunks:
            log.warning(
                "generate_content.no_source_chunks",
                content_id=content_id,
                source_type=row.source_type,
                source_id=str(row.source_id),
            )

        # Dispatch to the appropriate generator
        result = asyncio.run(
            _dispatch(
                content_type=row.content_type,
                style=row.style,
                source_chunks=source_chunks,
                strict_mode=strict_mode,
                platform=platform,
                length=length,
            )
        )

        row.content_json = result.get("content")
        row.fidelity_flags = result.get("fidelity_flags", [])
        row.file_path = result.get("file_path")
        row.source_chunks = source_chunks  # persist snapshot
        row.status = "complete"
        session.commit()

        log.info(
            "generate_content.done",
            content_id=content_id,
            content_type=row.content_type,
            style=row.style,
            chunks=len(source_chunks),
        )
        return content_id

    except Exception as exc:
        session.rollback()
        TASK_FAILURES.labels(task="generate_content").inc()
        log.exception("generate_content.failed", content_id=content_id)

        # Try to mark the row as failed
        try:
            row2: GeneratedContent | None = session.get(GeneratedContent, uuid.UUID(content_id))
            if row2 is not None:
                row2.status = "failed"
                session.commit()
        except Exception:
            pass

        try:
            import sentry_sdk
            sentry_sdk.capture_exception(exc)
        except Exception:
            pass

        raise
    finally:
        session.close()


async def _dispatch(
    content_type: str,
    style: str,
    source_chunks: list[dict],
    strict_mode: bool = False,
    platform: str | None = None,
    length: str = "short",
) -> dict:
    """Async dispatcher — routes to the correct generator function."""
    from app.services.content_engine import (
        generate_caption,
        generate_meme,
        generate_reel_script,
        generate_storyboard,
        generate_thread,
    )

    if content_type == "reel_script":
        return await generate_reel_script(source_chunks, style, length=length)

    if content_type == "meme":
        return await generate_meme(source_chunks, style)

    if content_type == "thread":
        if platform:
            return await generate_thread(source_chunks, style, platform=platform)
        return await generate_thread(source_chunks, style)

    if content_type == "storyboard":
        return await generate_storyboard(source_chunks, style)

    if content_type == "caption":
        if platform:
            return await generate_caption(source_chunks, style, platform=platform)
        return await generate_caption(source_chunks, style)

    raise ValueError(f"Unknown content_type: {content_type}")
