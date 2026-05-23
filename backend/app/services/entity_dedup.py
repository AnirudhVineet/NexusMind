"""Entity deduplication.

For each candidate entity (surface form + type + user_id), we either:
- merge into an existing row when both
    - cosine(new_embedding, existing.embedding) >= ENTITY_DEDUP_COSINE_THRESHOLD
    - rapidfuzz.token_sort_ratio(new_canonical, existing.canonical_name) >= ENTITY_DEDUP_FUZZ_THRESHOLD
  and record the new surface form as an alias if it isn't already; OR
- create a new entity row.

Only entities of the same `type` and `user_id` are ever considered for merging.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.entity import Entity, EntityAlias

log = get_logger(__name__)


def canonicalize(name: str) -> str:
    return " ".join(name.lower().strip().split())


@dataclass
class DedupResult:
    entity_id: uuid.UUID
    created: bool   # True if newly inserted, False if merged into existing


# How many candidate neighbours to pull from the HNSW index before applying
# the rapidfuzz string filter. 5 is plenty — cosine ≥ 0.92 is already strict.
_CANDIDATE_K = 5


def upsert_entity(
    session: Session,
    *,
    user_id: uuid.UUID,
    surface_form: str,
    entity_type: str,
    embedding: list[float],
) -> DedupResult:
    """Either merge `surface_form` into an existing entity or create a new one.

    Caller is responsible for committing the transaction.
    """
    settings = get_settings()
    canonical = canonicalize(surface_form)

    candidates = session.execute(
        select(
            Entity.id,
            Entity.canonical_name,
            (1.0 - Entity.embedding.cosine_distance(embedding)).label("cosine_sim"),
        )
        .where(Entity.user_id == user_id)
        .where(Entity.type == entity_type)
        .where(Entity.embedding.is_not(None))
        .order_by(Entity.embedding.cosine_distance(embedding))
        .limit(_CANDIDATE_K)
    ).all()

    for cand in candidates:
        sim = float(cand.cosine_sim) if cand.cosine_sim is not None else 0.0
        if sim < settings.entity_dedup_cosine_threshold:
            break  # ordered ascending distance == descending similarity
        fuzz_score = fuzz.token_sort_ratio(canonical, cand.canonical_name)
        if fuzz_score >= settings.entity_dedup_fuzz_threshold:
            # MERGE
            session.execute(
                Entity.__table__.update()
                .where(Entity.id == cand.id)
                .values(
                    evidence_count=Entity.evidence_count + 1,
                    last_seen_at=datetime.now(timezone.utc),
                )
            )
            # Record alias if different from canonical and not already present.
            session.execute(
                pg_insert(EntityAlias)
                .values(entity_id=cand.id, surface_form=surface_form)
                .on_conflict_do_nothing(constraint="uq_entity_aliases_form")
            )
            log.debug(
                "entity_dedup.merged",
                entity_id=str(cand.id),
                surface=surface_form,
                cosine=round(sim, 3),
                fuzz=fuzz_score,
            )
            return DedupResult(entity_id=cand.id, created=False)

    # INSERT new entity.
    new_id = uuid.uuid4()
    session.execute(
        Entity.__table__.insert().values(
            id=new_id,
            user_id=user_id,
            name=surface_form,
            canonical_name=canonical,
            type=entity_type,
            embedding=embedding,
            evidence_count=1,
        )
    )
    log.debug("entity_dedup.created", entity_id=str(new_id), surface=surface_form)
    return DedupResult(entity_id=new_id, created=True)
