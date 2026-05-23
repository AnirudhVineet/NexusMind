"""Retrieval service — Phase 3.1: hybrid BM25 + vector + RRF + reranker."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.metrics import (
    RETRIEVAL_DURATION,
)

if TYPE_CHECKING:
    pass

log = get_logger(__name__)


@dataclass
class SearchFilters:
    source_type: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    topic_tag: str | None = None
    min_credibility: float | None = None
    entity_id: uuid.UUID | None = None
    document_ids: list[uuid.UUID] = field(default_factory=list)


@dataclass
class RetrievalHit:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    page_number: int | None
    section: str | None
    text: str
    similarity_score: float
    source_type: str = ""
    credibility_score: float | None = None
    topic_tags: list[str] = field(default_factory=list)


def _vec_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in vec) + "]"


def _build_filter_clauses(filters: SearchFilters | None) -> tuple[str, dict]:
    """Return (extra_sql_clauses, params) for both BM25 and vector queries."""
    clauses: list[str] = []
    params: dict = {}

    if not filters:
        return "", params

    if filters.document_ids:
        clauses.append("AND c.document_id = ANY(:doc_ids)")
        params["doc_ids"] = [str(d) for d in filters.document_ids]

    if filters.source_type:
        clauses.append("AND d.source_type = :source_type")
        params["source_type"] = filters.source_type

    if filters.date_from:
        clauses.append("AND d.uploaded_at >= :date_from")
        params["date_from"] = filters.date_from

    if filters.date_to:
        clauses.append("AND d.uploaded_at <= :date_to")
        params["date_to"] = filters.date_to

    if filters.min_credibility is not None:
        clauses.append("AND d.credibility_score >= :min_cred")
        params["min_cred"] = filters.min_credibility

    if filters.topic_tag:
        # Check if topic_tag appears in d.intelligence->'topics' JSONB array
        clauses.append(
            "AND d.intelligence IS NOT NULL "
            "AND d.intelligence->'topics' ? :topic_tag"
        )
        params["topic_tag"] = filters.topic_tag

    if filters.entity_id:
        # Join via entity_edges/entity chunks linkage — filter documents whose
        # chunks mention this entity
        clauses.append(
            "AND EXISTS ("
            "  SELECT 1 FROM entities e "
            "  WHERE e.id = :entity_id "
            "  AND e.source_chunk_ids @> ARRAY[c.id]::uuid[]"
            ")"
        )
        params["entity_id"] = str(filters.entity_id)

    return " ".join(clauses), params


async def vector_search(
    session: AsyncSession,
    user_id: uuid.UUID,
    query_vec: list[float],
    top_k: int = 50,
    filters: SearchFilters | None = None,
) -> list[tuple[uuid.UUID, float]]:
    """Return (chunk_id, similarity_score) ordered by cosine similarity desc."""
    t0 = time.perf_counter()
    filter_sql, filter_params = _build_filter_clauses(filters)
    params: dict = {
        "user_id": str(user_id),
        "query_vec": _vec_literal(query_vec),
        "top_k": top_k,
        **filter_params,
    }

    sql = f"""
        SELECT c.id AS chunk_id,
               1 - (c.embedding <=> CAST(:query_vec AS vector)) AS score
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE c.user_id = :user_id
          AND c.embedding IS NOT NULL
          {filter_sql}
        ORDER BY c.embedding <=> CAST(:query_vec AS vector)
        LIMIT :top_k
    """
    rows = (await session.execute(text(sql), params)).mappings().all()
    RETRIEVAL_DURATION.labels(stage="vector").observe(time.perf_counter() - t0)
    return [(uuid.UUID(str(r["chunk_id"])), float(r["score"])) for r in rows]


async def bm25_search(
    session: AsyncSession,
    user_id: uuid.UUID,
    query: str,
    top_k: int = 50,
    filters: SearchFilters | None = None,
) -> list[tuple[uuid.UUID, float]]:
    """Return (chunk_id, bm25_score) ordered by ts_rank_cd desc."""
    t0 = time.perf_counter()
    filter_sql, filter_params = _build_filter_clauses(filters)
    params: dict = {
        "user_id": str(user_id),
        "query": query,
        "top_k": top_k,
        **filter_params,
    }

    sql = f"""
        SELECT c.id AS chunk_id,
               ts_rank_cd(c.tsv, plainto_tsquery('pg_catalog.english', :query)) AS score
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE c.user_id = :user_id
          AND c.tsv IS NOT NULL
          AND c.tsv @@ plainto_tsquery('pg_catalog.english', :query)
          {filter_sql}
        ORDER BY score DESC
        LIMIT :top_k
    """
    rows = (await session.execute(text(sql), params)).mappings().all()
    RETRIEVAL_DURATION.labels(stage="bm25").observe(time.perf_counter() - t0)
    return [(uuid.UUID(str(r["chunk_id"])), float(r["score"])) for r in rows]


def rrf_merge(
    rank_lists: list[list[uuid.UUID]],
    k: int = 60,
) -> list[uuid.UUID]:
    """Reciprocal Rank Fusion. Pure function — no I/O."""
    t0 = time.perf_counter()
    scores: dict[uuid.UUID, float] = {}
    for ranks in rank_lists:
        for pos, chunk_id in enumerate(ranks):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + pos + 1)
    result = [cid for cid, _ in sorted(scores.items(), key=lambda x: -x[1])]
    RETRIEVAL_DURATION.labels(stage="rrf").observe(time.perf_counter() - t0)
    return result


# Lazy-loaded reranker singleton
_reranker = None


def _get_reranker():
    global _reranker
    if _reranker is None:
        from sentence_transformers import CrossEncoder

        settings = get_settings()
        log.info("reranker.loading", model=settings.reranker_model)
        _reranker = CrossEncoder(settings.reranker_model, max_length=512)
        log.info("reranker.ready", model=settings.reranker_model)
    return _reranker


def rerank(
    query: str,
    hits: list[RetrievalHit],
    top_k: int = 10,
) -> list[RetrievalHit]:
    """Rerank hits using CrossEncoder. Falls back to original order if disabled."""
    settings = get_settings()
    if not settings.reranker_enabled or not hits:
        return hits[:top_k]

    t0 = time.perf_counter()
    pairs = [(query, h.text) for h in hits]
    scores = _get_reranker().predict(pairs, batch_size=16, show_progress_bar=False)
    ranked = sorted(zip(hits, scores), key=lambda x: -x[1])
    result = [h for h, _ in ranked[:top_k]]
    RETRIEVAL_DURATION.labels(stage="rerank").observe(time.perf_counter() - t0)
    return result


async def _load_hits(
    session: AsyncSession,
    user_id: uuid.UUID,
    chunk_ids: list[uuid.UUID],
) -> list[RetrievalHit]:
    """Fetch full chunk+document details for a ranked list of chunk IDs."""
    if not chunk_ids:
        return []

    id_strs = [str(cid) for cid in chunk_ids]
    sql = """
        SELECT c.id          AS chunk_id,
               c.document_id AS document_id,
               c.text        AS chunk_text,
               c.page_number AS page_number,
               c.section     AS section,
               d.filename    AS document_title,
               d.source_type AS source_type,
               d.credibility_score AS credibility_score,
               d.intelligence AS intelligence
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE c.user_id = :user_id
          AND c.id = ANY(:ids)
    """
    rows = (
        await session.execute(
            text(sql), {"user_id": str(user_id), "ids": id_strs}
        )
    ).mappings().all()

    # Build a lookup so we can return in ranked order
    by_id: dict[uuid.UUID, RetrievalHit] = {}
    for r in rows:
        intel = r["intelligence"] or {}
        topic_tags: list[str] = intel.get("topics", []) or []
        by_id[uuid.UUID(str(r["chunk_id"]))] = RetrievalHit(
            chunk_id=uuid.UUID(str(r["chunk_id"])),
            document_id=uuid.UUID(str(r["document_id"])),
            document_title=r["document_title"],
            page_number=r["page_number"],
            section=r["section"],
            text=r["chunk_text"],
            similarity_score=0.0,  # set below
            source_type=r["source_type"] or "",
            credibility_score=r["credibility_score"],
            topic_tags=topic_tags,
        )

    return [by_id[cid] for cid in chunk_ids if cid in by_id]


async def hybrid_search(
    session: AsyncSession,
    user_id: uuid.UUID,
    query: str,
    query_vec: list[float],
    top_k: int = 10,
    filters: SearchFilters | None = None,
) -> list[RetrievalHit]:
    """Full hybrid pipeline: vector + BM25 → RRF → reranker → top_k hits."""
    t_total = time.perf_counter()
    settings = get_settings()

    # Run vector and BM25 searches concurrently
    import asyncio

    vec_task = asyncio.create_task(
        vector_search(session, user_id, query_vec, settings.vector_top_k, filters)
    )
    bm25_task = asyncio.create_task(
        bm25_search(session, user_id, query, settings.bm25_top_k, filters)
    )
    vec_results, bm25_results = await asyncio.gather(vec_task, bm25_task)

    # RRF merge
    vec_ids = [cid for cid, _ in vec_results]
    bm25_ids = [cid for cid, _ in bm25_results]
    merged_ids = rrf_merge([vec_ids, bm25_ids], k=settings.rrf_k)

    # Cap at 30 before reranking
    rrf_top = merged_ids[:30]

    # Load full hit details
    hits = await _load_hits(session, user_id, rrf_top)

    # Attach similarity scores from vector results for confidence
    vec_score_map = {cid: s for cid, s in vec_results}
    for h in hits:
        h.similarity_score = vec_score_map.get(h.chunk_id, 0.5)

    # Rerank
    final = rerank(query, hits, top_k=settings.rerank_top_k)

    RETRIEVAL_DURATION.labels(stage="total").observe(time.perf_counter() - t_total)
    return final


# Legacy shim — keeps existing /qa callers working unchanged
async def search_chunks(
    session: AsyncSession,
    user_id: uuid.UUID,
    query_vec: list[float],
    top_k: int,
    document_ids: list[uuid.UUID] | None = None,
) -> list[RetrievalHit]:
    """Backwards-compatible wrapper used by existing /qa endpoint."""

    # We don't have the raw query string here, so reconstruct a best-effort
    # filters object from document_ids only
    filters = SearchFilters(document_ids=document_ids or [])

    # For the legacy path we skip BM25 (no query string available)
    vec_results = await vector_search(session, user_id, query_vec, top_k, filters)
    rrf_ids = [cid for cid, _ in vec_results]
    hits = await _load_hits(session, user_id, rrf_ids)
    vec_score_map = {cid: s for cid, s in vec_results}
    for h in hits:
        h.similarity_score = vec_score_map.get(h.chunk_id, 0.0)
    return hits
