"""Knowledge graph query helpers used by /api/graph and /api/entities/*."""
from __future__ import annotations

import re
import uuid
from typing import Optional

from sqlalchemy import desc, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.orm import aliased

from app.models.chunk import Chunk
from app.models.entity import ChunkEntity, Entity, EntityAlias
from app.models.entity_edge import EntityEdge


SNIPPET_WINDOW = 300

# Matches sentence boundaries: punctuation followed by whitespace + capital/quote.
# Deliberately conservative so "e.g." or "Fig. 3" don't trigger false splits.
_SENT_BOUNDARY = re.compile(r'(?<=[.!?])\s+(?=[A-Z"\'])')


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    start = 0
    for m in _SENT_BOUNDARY.finditer(text):
        spans.append((start, m.start() + 1))
        start = m.end()
    if start < len(text):
        spans.append((start, len(text)))
    return spans


def _snippet(chunk_text: str, start: int, end: int, window: int = SNIPPET_WINDOW) -> str:
    if not chunk_text:
        return ""

    sentences = _sentence_spans(chunk_text)
    lo: int
    hi: int

    if len(sentences) > 1:
        # Find all sentences that overlap the entity span.
        containing = [
            i for i, (s, e) in enumerate(sentences)
            if s <= end and e >= start
        ]
        if not containing:
            # Fallback: pick the closest sentence.
            containing = [
                min(
                    range(len(sentences)),
                    key=lambda i: min(
                        abs(sentences[i][0] - start),
                        abs(sentences[i][1] - end),
                    ),
                )
            ]
        # Include one sentence of context on each side.
        first = max(0, containing[0] - 1)
        last = min(len(sentences) - 1, containing[-1] + 1)
        lo, _ = sentences[first]
        _, hi = sentences[last]
        # Still over budget? Drop the context sentences.
        if hi - lo > window:
            lo, _ = sentences[containing[0]]
            _, hi = sentences[containing[-1]]
    else:
        center = (start + end) // 2
        half = window // 2
        lo = max(0, center - half)
        hi = min(len(chunk_text), center + half)

    raw = chunk_text[lo:hi]
    # Remove PDF soft-hyphen line-breaks ("algo-\nrithm" → "algorithm").
    raw = re.sub(r'-\s*\n\s*', '', raw)
    # Collapse remaining whitespace runs to a single space.
    raw = re.sub(r'\s+', ' ', raw)
    snippet = raw.strip()
    if lo > 0:
        snippet = "…" + snippet
    if hi < len(chunk_text):
        snippet = snippet + "…"
    return snippet


async def initial_graph(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    document_id: Optional[uuid.UUID] = None,
    types: Optional[list[str]] = None,
    min_confidence: float = 0.7,
    limit: int = 200,
) -> tuple[list[dict], list[dict]]:
    """Return the top-N entities by evidence_count + the edges between them."""
    if document_id is not None:
        entity_ids_subq = (
            select(ChunkEntity.entity_id)
            .join(Chunk, Chunk.id == ChunkEntity.chunk_id)
            .where(Chunk.document_id == document_id, Chunk.user_id == user_id)
            .distinct()
            .scalar_subquery()
        )
        stmt = select(Entity).where(Entity.user_id == user_id, Entity.id.in_(entity_ids_subq))
    else:
        stmt = select(Entity).where(Entity.user_id == user_id)
    if types:
        stmt = stmt.where(Entity.type.in_(types))
    stmt = stmt.order_by(desc(Entity.evidence_count)).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()

    node_ids = [r.id for r in rows]
    if not node_ids:
        return [], []

    edges_stmt = (
        select(EntityEdge)
        .where(EntityEdge.user_id == user_id)
        .where(EntityEdge.src_id.in_(node_ids))
        .where(EntityEdge.dst_id.in_(node_ids))
        .where(EntityEdge.confidence >= min_confidence)
    )
    edges = (await session.execute(edges_stmt)).scalars().all()

    nodes = [
        {
            "id": str(r.id),
            "name": r.name,
            "type": r.type,
            "evidence_count": r.evidence_count,
        }
        for r in rows
    ]
    edges_out = [
        {
            "id": str(e.id),
            "src": str(e.src_id),
            "dst": str(e.dst_id),
            "relation": e.relation_type,
            "confidence": e.confidence,
        }
        for e in edges
    ]
    return nodes, edges_out


async def neighborhood(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    entity_id: uuid.UUID,
    depth: int = 1,
    min_confidence: float = 0.7,
    types: Optional[list[str]] = None,
    limit: int = 200,
) -> tuple[list[dict], list[dict]]:
    """BFS up to `depth` hops from `entity_id` via a recursive CTE.

    Capped at `limit` nodes by descending evidence_count.
    """
    depth = max(1, min(int(depth), 3))
    type_filter_sql = ""
    params: dict = {
        "root": str(entity_id),
        "user_id": str(user_id),
        "depth": depth,
        "min_conf": float(min_confidence),
        "limit": int(limit),
    }
    if types:
        type_filter_sql = "AND e.type = ANY(:types)"
        params["types"] = list(types)

    query = text(
        f"""
        WITH RECURSIVE reachable(entity_id, dist) AS (
            SELECT :root::uuid, 0
            UNION
            SELECT CASE
                       WHEN ee.src_id = r.entity_id THEN ee.dst_id
                       ELSE ee.src_id
                   END,
                   r.dist + 1
            FROM entity_edges ee
            JOIN reachable r
                 ON (ee.src_id = r.entity_id OR ee.dst_id = r.entity_id)
            WHERE ee.user_id = :user_id::uuid
              AND ee.confidence >= :min_conf
              AND r.dist < :depth
        )
        SELECT e.id, e.name, e.type, e.evidence_count
        FROM entities e
        JOIN reachable rch ON rch.entity_id = e.id
        WHERE e.user_id = :user_id::uuid
        {type_filter_sql}
        ORDER BY e.evidence_count DESC
        LIMIT :limit
        """
    )
    node_rows = (await session.execute(query, params)).all()
    node_ids = [r[0] for r in node_rows]
    if not node_ids:
        return [], []

    edges_stmt = (
        select(EntityEdge)
        .where(EntityEdge.user_id == user_id)
        .where(EntityEdge.src_id.in_(node_ids))
        .where(EntityEdge.dst_id.in_(node_ids))
        .where(EntityEdge.confidence >= min_confidence)
    )
    edges = (await session.execute(edges_stmt)).scalars().all()

    nodes = [
        {
            "id": str(row[0]),
            "name": row[1],
            "type": row[2],
            "evidence_count": int(row[3]),
        }
        for row in node_rows
    ]
    edges_out = [
        {
            "id": str(e.id),
            "src": str(e.src_id),
            "dst": str(e.dst_id),
            "relation": e.relation_type,
            "confidence": e.confidence,
        }
        for e in edges
    ]
    return nodes, edges_out


async def entity_detail(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    entity_id: uuid.UUID,
    evidence_limit: int = 25,
    neighbor_limit: int = 50,
) -> Optional[dict]:
    entity = (
        await session.execute(
            select(Entity).where(Entity.id == entity_id, Entity.user_id == user_id)
        )
    ).scalar_one_or_none()
    if entity is None:
        return None

    aliases = (
        (
            await session.execute(
                select(EntityAlias.surface_form).where(EntityAlias.entity_id == entity.id)
            )
        )
        .scalars()
        .all()
    )

    evidence_rows = (
        await session.execute(
            select(
                Chunk.id,
                Chunk.document_id,
                Chunk.page_number,
                Chunk.text_content,
                ChunkEntity.char_start,
                ChunkEntity.char_end,
            )
            .join(ChunkEntity, ChunkEntity.chunk_id == Chunk.id)
            .where(ChunkEntity.entity_id == entity.id)
            .where(Chunk.user_id == user_id)
            .order_by(Chunk.created_at.desc())
            .limit(evidence_limit)
        )
    ).all()

    evidence = [
        {
            "chunk_id": str(row[0]),
            "document_id": str(row[1]),
            "page": row[2],
            "snippet": _snippet(row[3] or "", int(row[4]), int(row[5])),
        }
        for row in evidence_rows
    ]

    # Outgoing + incoming neighbors via aliased entity join.
    out_rows = (
        await session.execute(
            select(
                Entity.id,
                Entity.name,
                Entity.type,
                EntityEdge.relation_type,
                EntityEdge.confidence,
            )
            .join(EntityEdge, EntityEdge.dst_id == Entity.id)
            .where(EntityEdge.src_id == entity.id)
            .where(EntityEdge.user_id == user_id)
            .order_by(EntityEdge.confidence.desc())
            .limit(neighbor_limit)
        )
    ).all()
    in_rows = (
        await session.execute(
            select(
                Entity.id,
                Entity.name,
                Entity.type,
                EntityEdge.relation_type,
                EntityEdge.confidence,
            )
            .join(EntityEdge, EntityEdge.src_id == Entity.id)
            .where(EntityEdge.dst_id == entity.id)
            .where(EntityEdge.user_id == user_id)
            .order_by(EntityEdge.confidence.desc())
            .limit(neighbor_limit)
        )
    ).all()

    neighbors = [
        {
            "entity_id": str(r[0]),
            "name": r[1],
            "type": r[2],
            "relation": r[3],
            "confidence": float(r[4]),
            "direction": "out",
        }
        for r in out_rows
    ] + [
        {
            "entity_id": str(r[0]),
            "name": r[1],
            "type": r[2],
            "relation": r[3],
            "confidence": float(r[4]),
            "direction": "in",
        }
        for r in in_rows
    ]

    return {
        "id": str(entity.id),
        "name": entity.name,
        "canonical_name": entity.canonical_name,
        "type": entity.type,
        "evidence_count": entity.evidence_count,
        "aliases": list(aliases),
        "evidence": evidence,
        "neighbors": neighbors,
    }


async def edge_detail(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    edge_id: uuid.UUID,
) -> Optional[dict]:
    SrcEntity = aliased(Entity)
    DstEntity = aliased(Entity)
    row = (
        await session.execute(
            select(EntityEdge, Chunk, SrcEntity.name, DstEntity.name)
            .join(Chunk, Chunk.id == EntityEdge.evidence_chunk_id)
            .join(SrcEntity, SrcEntity.id == EntityEdge.src_id)
            .join(DstEntity, DstEntity.id == EntityEdge.dst_id)
            .where(EntityEdge.id == edge_id, EntityEdge.user_id == user_id)
        )
    ).first()
    if row is None:
        return None
    edge, chunk, src_name, dst_name = row
    # No specific char span on the edge — use the first ChunkEntity span for
    # the src entity, else the head of the chunk.
    span_row = (
        await session.execute(
            select(ChunkEntity.char_start, ChunkEntity.char_end)
            .where(ChunkEntity.chunk_id == chunk.id, ChunkEntity.entity_id == edge.src_id)
            .limit(1)
        )
    ).first()
    if span_row is not None:
        start, end = int(span_row[0]), int(span_row[1])
    else:
        start, end = 0, min(len(chunk.text_content), SNIPPET_WINDOW)
    return {
        "id": str(edge.id),
        "src_id": str(edge.src_id),
        "dst_id": str(edge.dst_id),
        "src_name": src_name or "Unknown",
        "dst_name": dst_name or "Unknown",
        "relation": edge.relation_type,
        "confidence": edge.confidence,
        "evidence_chunk_id": str(chunk.id),
        "evidence_document_id": str(chunk.document_id),
        "evidence_page": chunk.page_number,
        "evidence_snippet": _snippet(chunk.text_content or "", start, end),
        "justification": edge.justification,
    }
