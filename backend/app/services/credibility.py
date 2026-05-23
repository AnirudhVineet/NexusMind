"""Source credibility scoring service.

Computes a composite [0,1] credibility score for a document from three signals:
  1. recency          – exponential decay from upload date
  2. source_type      – heuristic signal from MIME / URL pattern lookup
  3. citation_density – fraction of document entities also seen in other docs

Weights are read from Redis (key: credibility:weights:current) and fall back
to settings defaults if the key is absent.  The computed score and breakdown
are stored on documents.credibility_score / credibility_breakdown.

(The Phase 2.5 `cross_source_agreement` signal was removed alongside the
Conflicts feature — it relied on the claims/claim_contradictions tables.
Any `cross_source_agreement` weight in Redis or settings is silently
ignored and its weight share is redistributed across the remaining
signals so the final score still lands in [0,1].)
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.metrics import CREDIBILITY_SCORE, SOURCE_TYPE_MATCH
from app.models.document import Document
from app.models.source_type_signal import SourceTypeSignal

log = get_logger(__name__)

_WEIGHTS_REDIS_KEY = "credibility:weights:current"
_WEIGHTS_VERSION_KEY = "credibility:weights:version"
_DEFAULT_WEIGHTS_VERSION = "default"

# Weights we actually use. Anything else in the loaded weights dict (e.g. a
# stale `cross_source_agreement` value left in Redis from before Conflicts
# was removed) is dropped before computing the score.
_ACTIVE_SIGNALS = ("recency", "source_type", "citation_density")


def _default_weights() -> dict[str, float]:
    s = get_settings()
    return {
        "recency": s.credibility_weight_recency,
        "source_type": s.credibility_weight_source_type,
        "citation_density": s.credibility_weight_citation_density,
    }


def _normalize_weights(raw: dict[str, float]) -> dict[str, float]:
    """Keep only active signals and re-normalize so they sum to 1.0.

    If the configured weights happen to sum to 0 (or only contain inactive
    keys), fall back to an even split.
    """
    filtered = {k: float(raw.get(k, 0.0)) for k in _ACTIVE_SIGNALS}
    total = sum(filtered.values())
    if total <= 0:
        even = 1.0 / len(_ACTIVE_SIGNALS)
        return {k: even for k in _ACTIVE_SIGNALS}
    return {k: v / total for k, v in filtered.items()}


def get_weights() -> tuple[dict[str, float], str]:
    """Return (weights_dict, version_string).  Falls back to settings defaults.

    The returned dict is normalized: only active signals are included and
    their values sum to 1.0.
    """
    try:
        import json
        import redis as redis_lib

        s = get_settings()
        r = redis_lib.from_url(s.redis_url, decode_responses=True)
        raw = r.get(_WEIGHTS_REDIS_KEY)
        version = r.get(_WEIGHTS_VERSION_KEY) or _DEFAULT_WEIGHTS_VERSION
        if raw:
            return _normalize_weights(json.loads(raw)), version
    except Exception:
        pass
    return _normalize_weights(_default_weights()), _DEFAULT_WEIGHTS_VERSION


# ---------------------------------------------------------------------------
# Signal helpers
# ---------------------------------------------------------------------------

def _resolve_source_type_signal(
    session: Session, doc: Document
) -> tuple[float, str, int]:
    """Return (signal_value, source_label, half_life_days) for a document.

    Matches by MIME type or URL (when available) using source_type_signals
    ordered by ascending priority (lower = higher precedence).
    """
    signals = session.execute(
        select(SourceTypeSignal).order_by(SourceTypeSignal.priority.asc())
    ).scalars().all()

    mime = doc.mime_type or ""
    # Documents don't have a stored URL in the current schema; only MIME matching
    # is used.  URL matching can be wired in when web ingestion lands.
    for sig in signals:
        if sig.match_kind == "mime" and sig.match_value == mime:
            SOURCE_TYPE_MATCH.labels(source_label=sig.source_label).inc()
            return sig.signal_value, sig.source_label, sig.half_life_days
        if sig.match_kind == "host_regex":
            # Catch-all fallback
            if sig.match_value == ".*":
                SOURCE_TYPE_MATCH.labels(source_label=sig.source_label).inc()
                return sig.signal_value, sig.source_label, sig.half_life_days

    SOURCE_TYPE_MATCH.labels(source_label="unknown").inc()
    return 0.50, "unknown", 180


def _recency_signal(doc: Document, half_life_days: int) -> tuple[float, int]:
    now = datetime.now(timezone.utc)
    ts = doc.uploaded_at
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    age_days = (now - ts).days
    value = math.exp(-age_days / max(half_life_days, 1))
    return value, age_days


def _citation_density_signal(
    session: Session, document_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[float, int, int]:
    """Return (signal_value, shared_entities, total_entities)."""
    total_entities = session.execute(
        text(
            """
            SELECT COUNT(DISTINCT ce.entity_id)
            FROM chunk_entities ce
            JOIN chunks c ON c.id = ce.chunk_id
            WHERE c.document_id = :document_id
              AND c.user_id     = :user_id
            """
        ),
        {"document_id": str(document_id), "user_id": str(user_id)},
    ).scalar_one() or 0

    shared_entities = session.execute(
        text(
            """
            SELECT COUNT(DISTINCT ce_self.entity_id)
            FROM chunk_entities ce_self
            JOIN chunks c_self ON c_self.id = ce_self.chunk_id
            WHERE c_self.document_id = :document_id
              AND c_self.user_id     = :user_id
              AND EXISTS (
                  SELECT 1 FROM chunk_entities ce_other
                  JOIN chunks c_other ON c_other.id = ce_other.chunk_id
                  WHERE ce_other.entity_id  = ce_self.entity_id
                    AND c_other.document_id != :document_id
                    AND c_other.user_id     = :user_id
              )
            """
        ),
        {"document_id": str(document_id), "user_id": str(user_id)},
    ).scalar_one() or 0

    density = shared_entities / max(total_entities, 1)
    return density, int(shared_entities), int(total_entities)


# ---------------------------------------------------------------------------
# Main computation
# ---------------------------------------------------------------------------

def compute_credibility(
    session: Session, document_id: uuid.UUID, user_id: uuid.UUID
) -> dict[str, Any]:
    """Compute all credibility signals and write score + breakdown to document.

    Returns the breakdown dict.
    """
    doc = session.get(Document, document_id)
    if doc is None:
        raise RuntimeError(f"Document {document_id} not found")

    weights, weights_version = get_weights()

    # Individual signals.
    source_val, source_label, half_life = _resolve_source_type_signal(session, doc)
    recency_val, age_days = _recency_signal(doc, half_life)
    density_val, shared_ents, total_ents = _citation_density_signal(
        session, document_id, user_id
    )

    score = (
        weights["recency"] * recency_val
        + weights["source_type"] * source_val
        + weights["citation_density"] * density_val
    )
    score = max(0.0, min(1.0, score))

    breakdown: dict[str, Any] = {
        "recency": {
            "value": round(recency_val, 4),
            "weight": weights["recency"],
            "age_days": age_days,
            "half_life_days": half_life,
        },
        "source_type": {
            "value": round(source_val, 4),
            "weight": weights["source_type"],
            "label": source_label,
        },
        "citation_density": {
            "value": round(density_val, 4),
            "weight": weights["citation_density"],
            "shared_entities": shared_ents,
            "total_entities": total_ents,
        },
        "weights_version": weights_version,
        "score": round(score, 4),
    }

    doc.credibility_score = score
    doc.credibility_breakdown = breakdown
    doc.credibility_computed_at = datetime.now(timezone.utc)
    session.commit()

    CREDIBILITY_SCORE.observe(score)
    log.info(
        "credibility.computed",
        document_id=str(document_id),
        score=round(score, 3),
        source_label=source_label,
    )
    return breakdown


def score_label(score: float) -> str:
    if score < 0.4:
        return "low"
    if score < 0.65:
        return "moderate"
    if score < 0.85:
        return "high"
    return "very_high"


def find_neighbor_documents(
    session: Session,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
    max_neighbors: int = 50,
) -> list[uuid.UUID]:
    """Return doc IDs that share at least one entity with this document."""
    rows = session.execute(
        text(
            """
            SELECT DISTINCT c_other.document_id
            FROM chunk_entities ce_self
            JOIN chunks c_self  ON c_self.id  = ce_self.chunk_id
            JOIN chunk_entities ce_other ON ce_other.entity_id = ce_self.entity_id
            JOIN chunks c_other ON c_other.id  = ce_other.chunk_id
            WHERE c_self.document_id  = :document_id
              AND c_self.user_id      = :user_id
              AND c_other.document_id != :document_id
              AND c_other.user_id     = :user_id
            LIMIT :limit
            """
        ),
        {
            "document_id": str(document_id),
            "user_id": str(user_id),
            "limit": max_neighbors,
        },
    ).fetchall()
    return [uuid.UUID(str(r[0])) for r in rows]
