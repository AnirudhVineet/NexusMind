"""Relation extraction Celery worker.

For each chunk that has at least 2 entities, prompt the local LLM (Qwen2.5
via Ollama, JSON mode) to emit typed relations between the entity pairs.
Output is filtered against the closed taxonomy and the configured minimum
confidence; surviving relations land in `entity_edges`.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging, get_logger
from app.core.metrics import (
    INGEST_PAUSED,
    OLLAMA_TOKENS_PER_CHUNK,
    OLLAMA_TOKENS_PER_SECOND,
    TASK_FAILURES,
)
from app.db.sync_session import get_sync_session
from app.models.chunk import Chunk
from app.models.entity import ChunkEntity, Entity
from app.models.entity_edge import RELATION_TYPES, EntityEdge
from app.services.llm_local import build_user_prompt, call_json_sync
from app.workers.celery_app import celery_app
from app.workers.idempotency import idempotent_task

configure_logging()
log = get_logger(__name__)


# Schema sent to the LLM as the expected output shape.
_REL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["relations"],
    "properties": {
        "relations": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "src",
                    "dst",
                    "relation_type",
                    "confidence",
                    "justification",
                ],
                "properties": {
                    "src": {"type": "string", "description": "source entity name"},
                    "dst": {
                        "type": "string",
                        "description": "destination entity name",
                    },
                    "relation_type": {
                        "type": "string",
                        "enum": list(RELATION_TYPES),
                    },
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "justification": {
                        "type": "string",
                        "description": "short quote from the chunk supporting the relation",
                    },
                },
            },
        }
    },
}


_TASK_INSTRUCTION = (
    "Given the entities below, identify every typed relation between pairs "
    "of them that is directly supported by the document text. Only emit "
    "relations of the allowed types. Each relation must include a brief "
    "justification quoted from the text. If no valid relations exist, return "
    '{"relations": []}.'
)


def _format_entity_list(entities: list[Entity]) -> str:
    lines = [f"- {e.name} ({e.type})" for e in entities]
    return "\n".join(lines)


def _check_backpressure(self) -> None:
    """Pause if the relations queue is too deep.

    Uses Celery's broker inspect API; if it fails for any reason we err on the
    side of running (don't block the pipeline on a transient broker error).
    """
    settings = get_settings()
    try:
        # `current_app.control.inspect()` requires a workers running with -E.
        inspector = self.app.control.inspect(timeout=1.0)
        reserved = inspector.reserved() or {}
        active = inspector.active() or {}
        depth = 0
        for worker_tasks in list(reserved.values()) + list(active.values()):
            for t in worker_tasks or []:
                if (t.get("delivery_info") or {}).get("routing_key") == "relations":
                    depth += 1
        if depth > settings.relation_queue_backpressure_depth:
            INGEST_PAUSED.labels(reason="relations_backpressure").inc()
            raise AppError(
                "relations queue saturated; retry later",
                status_code=503,
                code="relations_backpressure",
            )
    except AppError:
        raise
    except Exception:
        # broker introspection failed; proceed
        return


def _process_chunk(session, chunk: Chunk) -> int:
    """Prompt the LLM for relations in this chunk; insert surviving edges.

    Returns the number of edges inserted.
    """
    entity_rows = list(
        session.execute(
            select(Entity)
            .join(ChunkEntity, ChunkEntity.entity_id == Entity.id)
            .where(ChunkEntity.chunk_id == chunk.id)
            .distinct()
        ).scalars()
    )
    if len(entity_rows) < 2:
        return 0

    settings = get_settings()
    user_prompt = build_user_prompt(
        chunk_text=chunk.text_content,
        task_instruction=_TASK_INSTRUCTION + "\n\nEntities:\n" + _format_entity_list(entity_rows),
        json_schema=_REL_SCHEMA,
    )

    try:
        response = call_json_sync(
            system=None,
            user=user_prompt,
            schema_hint=_REL_SCHEMA,
            task_label="relations",
        )
    except Exception as e:
        log.warning(
            "relations.llm_call_failed", chunk_id=str(chunk.id), error=str(e)
        )
        return 0

    if response.usage and response.usage.duration_s > 0:
        OLLAMA_TOKENS_PER_SECOND.labels(task="relations").observe(
            response.usage.completion_tokens / response.usage.duration_s
        )
        OLLAMA_TOKENS_PER_CHUNK.labels(task="relations").observe(
            response.usage.total_tokens
        )

    relations = (response.parsed or {}).get("relations") or []
    if not isinstance(relations, list):
        log.warning(
            "relations.bad_shape",
            chunk_id=str(chunk.id),
            raw=response.raw[:200],
        )
        return 0

    name_to_id = {e.name: e.id for e in entity_rows}
    name_lower_to_id = {e.name.lower(): e.id for e in entity_rows}

    written = 0
    for rel in relations:
        if not isinstance(rel, dict):
            continue
        rtype = (rel.get("relation_type") or "").strip()
        if rtype not in RELATION_TYPES:
            continue
        try:
            confidence = float(rel.get("confidence", 0))
        except (TypeError, ValueError):
            continue
        if confidence < settings.relation_min_confidence or confidence > 1.0:
            continue
        src_name = (rel.get("src") or "").strip()
        dst_name = (rel.get("dst") or "").strip()
        if not src_name or not dst_name or src_name == dst_name:
            continue
        src_id = name_to_id.get(src_name) or name_lower_to_id.get(src_name.lower())
        dst_id = name_to_id.get(dst_name) or name_lower_to_id.get(dst_name.lower())
        if src_id is None or dst_id is None:
            continue
        justification = (rel.get("justification") or "").strip()[:1000]
        if not justification:
            continue

        result = session.execute(
            pg_insert(EntityEdge)
            .values(
                user_id=chunk.user_id,
                src_id=src_id,
                dst_id=dst_id,
                relation_type=rtype,
                confidence=confidence,
                evidence_chunk_id=chunk.id,
                justification=justification,
            )
            .on_conflict_do_nothing(constraint="uq_entity_edges_dedup")
        )
        if result.rowcount:
            written += 1

    return written


@celery_app.task(
    name="extract_relations",
    bind=True,
    queue="relations",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=3,
)
def extract_relations_task(self, document_id: str) -> str:
    _check_backpressure(self)

    session = get_sync_session()
    try:
        with idempotent_task(
            session, "document", document_id, "extract_relations"
        ) as ctx:
            if ctx.skipped:
                return document_id

            chunks = list(
                session.execute(
                    select(Chunk)
                    .where(Chunk.document_id == uuid.UUID(document_id))
                    .order_by(Chunk.chunk_index)
                ).scalars()
            )

            total_edges = 0
            for chunk in chunks:
                inserted = _process_chunk(session, chunk)
                total_edges += inserted
                session.commit()

            log.info(
                "extract_relations.done",
                document_id=document_id,
                chunks=len(chunks),
                edges_written=total_edges,
            )
        return document_id

    except Exception as e:
        session.rollback()
        TASK_FAILURES.labels(task="extract_relations").inc()
        log.exception("extract_relations.failed", document_id=document_id)
        try:
            import sentry_sdk

            sentry_sdk.capture_exception(e)
        except Exception:
            pass
        raise
    finally:
        session.close()
