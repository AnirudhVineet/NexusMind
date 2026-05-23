"""Document intelligence: multi-level summaries, key insights, tags, metrics.

Used by the `compute_intelligence` Celery task. Calls Ollama (Qwen2.5) for
LLM-driven outputs and `textstat` + spaCy for cheap local computations.

The orchestrator is deliberately small: each helper handles one level of the
output, and `compute_for_document` assembles them into a single JSONB blob.
"""
from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.metrics import OLLAMA_TOKENS_PER_CHUNK, OLLAMA_TOKENS_PER_SECOND
from app.models.chunk import Chunk
from app.models.entity import ChunkEntity, Entity
from app.services.llm_local import call_json_sync, call_text_sync

log = get_logger(__name__)


# Rough token estimate: 1 token ≈ 4 chars for English text. Good enough to
# decide whether to map-reduce vs. one-shot.
def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _word_count(text: str) -> int:
    return len(re.findall(r"\w+", text))


# ---------------------------------------------------------------------------
# Chunk collation
# ---------------------------------------------------------------------------

def _load_chunks(session: Session, document_id: uuid.UUID) -> list[Chunk]:
    return list(
        session.execute(
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.chunk_index)
        ).scalars()
    )


def _document_text(chunks: list[Chunk]) -> str:
    return "\n\n".join(c.text_content for c in chunks if c.text_content)


# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------

_ABSTRACT_SYS = (
    "You write single-sentence abstracts of documents. Output exactly one "
    "sentence of at most 30 words. No preamble, no markdown, no trailing "
    "newline."
)
_SUMMARY_SYS = (
    "You write 3-5 bullet executive summaries of documents. Each bullet is "
    "one tight sentence (max 20 words). Output bullets only, one per line, "
    "each prefixed by '- '. No preamble."
)
_DEEP_DIVE_SYS = (
    "You write structured deep-dive summaries. Group content into 2-6 "
    "sections, each headed by '## <Section Name>' followed by 2-4 sentences. "
    "Cover what the document is about, its main claims, and any limitations. "
    "Use only what the document supplies."
)


def _summarize(text: str, system: str, task_label: str) -> str:
    user = f"Document:\n\n{text}\n\nProduce the requested output."
    content, _ = call_text_sync(system=system, user=user, task_label=task_label)
    return content.strip()


def _map_reduce_summarize(chunks: list[Chunk], system: str, task_label: str) -> str:
    """Map: per-chunk summaries. Reduce: summarise the chunk summaries."""
    partials: list[str] = []
    for c in chunks:
        if not c.text_content or not c.text_content.strip():
            continue
        partials.append(
            _summarize(c.text_content, _ABSTRACT_SYS, f"{task_label}_partial")
        )
    joined = "\n".join(f"- {p}" for p in partials)
    return _summarize(joined, system, f"{task_label}_reduce")


def _generate_summaries(chunks: list[Chunk]) -> dict[str, Any]:
    settings = get_settings()
    full_text = _document_text(chunks)
    if not full_text.strip():
        return {"abstract": "", "summary": [], "deep_dive": ""}

    threshold = settings.intelligence_map_reduce_token_threshold
    long_doc = _approx_tokens(full_text) > threshold

    if long_doc:
        abstract = _map_reduce_summarize(chunks, _ABSTRACT_SYS, "summary_abstract")
        deep_dive = _map_reduce_summarize(chunks, _DEEP_DIVE_SYS, "summary_deep")
        bullets_raw = _map_reduce_summarize(chunks, _SUMMARY_SYS, "summary_bullets")
    else:
        abstract = _summarize(full_text, _ABSTRACT_SYS, "summary_abstract")
        deep_dive = _summarize(full_text, _DEEP_DIVE_SYS, "summary_deep")
        bullets_raw = _summarize(full_text, _SUMMARY_SYS, "summary_bullets")

    bullets = [
        line.lstrip("-• ").strip()
        for line in bullets_raw.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    return {
        "abstract": abstract.strip(),
        "summary": [b for b in bullets if b][:5],
        "deep_dive": deep_dive.strip(),
    }


# ---------------------------------------------------------------------------
# Key insights
# ---------------------------------------------------------------------------

_INSIGHTS_SCHEMA = {
    "type": "object",
    "required": ["insights"],
    "properties": {
        "insights": {
            "type": "array",
            "maxItems": 5,
            "items": {
                "type": "object",
                "required": ["claim", "source_chunk_index", "confidence"],
                "properties": {
                    "claim": {"type": "string"},
                    "source_chunk_index": {"type": "integer"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
            },
        }
    },
}


def _generate_key_insights(chunks: list[Chunk]) -> list[dict[str, Any]]:
    if not chunks:
        return []

    numbered = "\n\n".join(
        f"[chunk {c.chunk_index}]\n{c.text_content or ''}" for c in chunks
    )
    user = (
        "From the document below, extract the top 5 most information-dense "
        "claims. For each, give the exact claim text, the chunk index it "
        "comes from, and a 0-1 confidence score.\n\n"
        f"<document>\n{numbered}\n</document>\n\nRespond ONLY with JSON "
        "matching the schema."
    )
    try:
        response = call_json_sync(
            system=None,
            user=user,
            schema_hint=_INSIGHTS_SCHEMA,
            task_label="key_insights",
        )
    except Exception:
        log.exception("intelligence.key_insights.llm_failed")
        return []

    if response.usage and response.usage.duration_s > 0:
        OLLAMA_TOKENS_PER_SECOND.labels(task="key_insights").observe(
            response.usage.completion_tokens / response.usage.duration_s
        )
        OLLAMA_TOKENS_PER_CHUNK.labels(task="key_insights").observe(
            response.usage.total_tokens
        )

    index_to_id = {c.chunk_index: c.id for c in chunks}
    insights_raw = (response.parsed or {}).get("insights") or []
    out: list[dict[str, Any]] = []
    for item in insights_raw:
        if not isinstance(item, dict):
            continue
        claim = (item.get("claim") or "").strip()
        if not claim:
            continue
        try:
            idx = int(item.get("source_chunk_index"))
            confidence = float(item.get("confidence", 0))
        except (TypeError, ValueError):
            continue
        chunk_id = index_to_id.get(idx)
        if chunk_id is None:
            continue
        out.append(
            {
                "claim": claim,
                "source_chunk_id": str(chunk_id),
                "confidence": max(0.0, min(1.0, confidence)),
            }
        )
    return out[:5]


# ---------------------------------------------------------------------------
# Topic tags (LLM zero-shot against a seed taxonomy; BERTopic refines later)
# ---------------------------------------------------------------------------

_TAGS_SCHEMA = {
    "type": "object",
    "required": ["tags"],
    "properties": {
        "tags": {
            "type": "array",
            "minItems": 3,
            "maxItems": 7,
            "items": {
                "type": "object",
                "required": ["slug", "display_name", "confidence"],
                "properties": {
                    "slug": {"type": "string"},
                    "display_name": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
            },
        }
    },
}


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    s = _SLUG_RE.sub("-", text.lower()).strip("-")
    return s[:64] or "tag"


def _generate_tags(text: str) -> list[dict[str, Any]]:
    if not text.strip():
        return []
    user = (
        "Pick 3-7 topic tags that best describe the document. Use short, "
        "lowercase kebab-case slugs. Each tag has a 0-1 confidence.\n\n"
        f"<document>\n{text[:8000]}\n</document>\n\nRespond ONLY with JSON."
    )
    try:
        response = call_json_sync(
            system=None, user=user, schema_hint=_TAGS_SCHEMA, task_label="tags"
        )
    except Exception:
        log.exception("intelligence.tags.llm_failed")
        return []
    raw = (response.parsed or {}).get("tags") or []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        display = (item.get("display_name") or "").strip()
        slug = _slugify(item.get("slug") or display)
        if not slug or slug in seen:
            continue
        try:
            confidence = float(item.get("confidence", 0))
        except (TypeError, ValueError):
            continue
        seen.add(slug)
        out.append(
            {
                "slug": slug,
                "display_name": display or slug,
                "confidence": max(0.0, min(1.0, confidence)),
            }
        )
    return out[:7]


# ---------------------------------------------------------------------------
# Reading metrics
# ---------------------------------------------------------------------------

def _reading_metrics(
    session: Session,
    document_id: uuid.UUID,
    text: str,
) -> dict[str, Any]:
    try:
        import textstat

        fk = float(textstat.flesch_kincaid_grade(text)) if text.strip() else 0.0
    except Exception:
        fk = 0.0

    words = _word_count(text)
    reading_minutes = max(1, round(words / 250))

    # Jargon density: count of distinct entities flagged on this doc / total
    # content words. Cheap; uses already-stored entities.
    entity_count = (
        session.execute(
            select(Entity.id)
            .join(ChunkEntity, ChunkEntity.entity_id == Entity.id)
            .join(Chunk, Chunk.id == ChunkEntity.chunk_id)
            .where(Chunk.document_id == document_id)
            .distinct()
        ).all()
    )
    jargon_density = (
        len(entity_count) / max(words, 1) if words else 0.0
    )
    return {
        "flesch_kincaid_grade": round(fk, 2),
        "reading_minutes": int(reading_minutes),
        "jargon_density": round(min(jargon_density, 1.0), 4),
    }


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def compute_for_document(session: Session, document_id: uuid.UUID) -> dict[str, Any]:
    chunks = _load_chunks(session, document_id)
    if not chunks:
        return {
            "abstract": "",
            "summary": [],
            "deep_dive": "",
            "key_insights": [],
            "tags": [],
            "metrics": {
                "flesch_kincaid_grade": 0.0,
                "reading_minutes": 0,
                "jargon_density": 0.0,
            },
        }

    full_text = _document_text(chunks)
    summaries = _generate_summaries(chunks)
    insights = _generate_key_insights(chunks)
    tags = _generate_tags(full_text)
    metrics = _reading_metrics(session, document_id, full_text)

    return {
        **summaries,
        "key_insights": insights,
        "tags": tags,
        "metrics": metrics,
    }
