"""Research Assistant service — Phase 4 Track B.

Provides three async pipeline stages:
  1. expand_query   — generate sub-questions from a research topic via Groq/Ollama
  2. gather_evidence — retrieve relevant chunks for each sub-question
  3. synthesize_brief — produce a structured ResearchBrief via Groq/Ollama
"""
from __future__ import annotations

import json
import re
import statistics
import uuid
from typing import Any

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.research import ResearchBrief
from app.services.embedding import get_embedding_service
from app.services.retrieval import SearchFilters, hybrid_search

log = get_logger(__name__)

_JSON_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)
_JSON_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)


class NoEvidenceError(Exception):
    """Raised when the user's library has no chunks matching the topic.

    The worker catches this and marks the brief failed with an actionable
    message rather than letting the LLM hallucinate a brief from nothing.
    """


def _groq_client() -> AsyncOpenAI:
    s = get_settings()
    return AsyncOpenAI(api_key=s.groq_api_key, base_url=s.groq_base_url)


def _ollama_client() -> AsyncOpenAI:
    s = get_settings()
    return AsyncOpenAI(api_key="ollama", base_url=s.ollama_base_url)


def _coerce_json(content: str) -> Any:
    content = content.strip()
    if not content:
        raise ValueError("empty LLM response")
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        for pat in (_JSON_ARRAY_RE, _JSON_OBJ_RE):
            m = pat.search(content)
            if m:
                return json.loads(m.group(0))
        raise


async def _chat_completion(
    client: AsyncOpenAI,
    messages: list[dict],
    *,
    provider: str = "groq",
    temperature: float = 0.2,
) -> str:
    settings = get_settings()
    model = settings.llm_model if provider == "groq" else settings.ollama_model_primary
    try:
        resp = await client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=messages,
        )
        return (resp.choices[0].message.content or "").strip()
    finally:
        try:
            await client.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Stage 1: Query expansion
# ---------------------------------------------------------------------------

async def expand_query(topic: str, n: int = 5) -> list[str]:
    """Return n sub-questions that together cover the research topic.

    Calls Groq first; falls back to Ollama on any exception.
    Returns [topic] if both fail.
    """
    prompt = (
        f"You are a research strategist. Given the research topic below, "
        f"generate exactly {n} focused sub-questions that together provide "
        f"comprehensive coverage of the topic. "
        f"Return ONLY a JSON array of {n} strings — no prose, no markdown fences.\n\n"
        f"Topic: {topic}"
    )
    messages = [
        {"role": "system", "content": "You output only valid JSON."},
        {"role": "user", "content": prompt},
    ]

    for client_factory, label in [(_groq_client, "groq"), (_ollama_client, "ollama")]:
        try:
            client = client_factory()
            raw = await _chat_completion(client, messages, provider=label, temperature=0.3)
            parsed = _coerce_json(raw)
            if isinstance(parsed, list) and all(isinstance(q, str) for q in parsed):
                return parsed
            log.warning("expand_query.unexpected_shape", provider=label, raw=raw[:200])
        except Exception as exc:
            log.warning("expand_query.failed", provider=label, error=str(exc))

    return [topic]


# ---------------------------------------------------------------------------
# Stage 2: Evidence gathering
# ---------------------------------------------------------------------------

async def gather_evidence(
    sub_queries: list[str],
    user_id: uuid.UUID,
    session: AsyncSession,
) -> list[dict]:
    """Retrieve chunks for each sub-query and deduplicate by chunk_id.

    Each returned dict is a RetrievalHit-derived dict with an added
    ``provenance`` field indicating the originating sub-query.
    """
    embedder = get_embedding_service()
    seen_chunk_ids: set[str] = set()
    results: list[dict] = []

    for sub_query in sub_queries:
        try:
            query_vec = await embedder.embed_query(sub_query)
            hits = await hybrid_search(
                session=session,
                user_id=user_id,
                query=sub_query,
                query_vec=query_vec,
                top_k=8,
                filters=SearchFilters(),
            )
            for hit in hits:
                cid = str(hit.chunk_id)
                if cid in seen_chunk_ids:
                    continue
                seen_chunk_ids.add(cid)
                results.append(
                    {
                        "chunk_id": str(hit.chunk_id),
                        "document_id": str(hit.document_id),
                        "document_title": hit.document_title,
                        "text_content": hit.text,
                        "score": hit.similarity_score,
                        "source_type": hit.source_type,
                        "provenance": sub_query,
                    }
                )
        except Exception as exc:
            log.warning("gather_evidence.sub_query_failed", sub_query=sub_query[:80], error=str(exc))

    return results


# ---------------------------------------------------------------------------
# Stage 3: Brief synthesis
# ---------------------------------------------------------------------------

def _build_synthesis_prompt(topic: str, chunks: list[dict]) -> str:
    chunk_lines: list[str] = []
    for chunk in chunks:
        cid = chunk["chunk_id"]
        text = chunk["text_content"][:400]
        title = chunk.get("document_title", "Unknown")
        chunk_lines.append(f"[{cid}] ({title}): {text}")

    chunks_block = "\n\n".join(chunk_lines)

    schema_example = json.dumps(
        {
            "topic": "<string>",
            "executive_summary": "<string, 3-5 sentences>",
            "key_arguments": [
                {
                    "claim": "<string>",
                    "evidence_chunk_ids": ["<chunk_id>"],
                    "stance": "supporting",
                }
            ],
            "counterarguments": [
                {
                    "claim": "<string>",
                    "evidence_chunk_ids": ["<chunk_id>"],
                    "stance": "opposing",
                }
            ],
            "knowledge_gaps": ["<string>"],
            "recommended_reading": [
                {"document_title": "<string>", "reason": "<string>"}
            ],
        },
        indent=2,
    )

    return (
        f"You are a research analyst. Using ONLY the evidence chunks below, "
        f"produce a research brief on the topic.\n\n"
        f"Topic: {topic}\n\n"
        f"--- EVIDENCE CHUNKS ---\n{chunks_block}\n--- END CHUNKS ---\n\n"
        f"RULES (MUST FOLLOW):\n"
        f"- Every claim in `key_arguments` and `counterarguments` MUST cite at "
        f"least one chunk_id from the EVIDENCE CHUNKS section above. "
        f"If you can't cite, omit the claim entirely.\n"
        f"- Do NOT invent claims, facts, numbers, or document titles not "
        f"present in the evidence.\n"
        f"- Use the chunk_id values EXACTLY as provided in square brackets — "
        f"no paraphrasing, no truncation.\n"
        f"- If the evidence is too sparse to form a coherent argument, set "
        f"`key_arguments` to an empty list and explain in `knowledge_gaps`.\n\n"
        f"Return ONLY valid JSON matching this schema (no markdown, no prose):\n"
        f"{schema_example}"
    )


def _compute_confidence(chunks: list[dict]) -> tuple[float, str]:
    """Score retrieval quality as the mean of the top-10 similarity scores,
    plus a small bonus for evidence breadth (unique documents).

    Returns (score in [0,1], human-readable band).
    """
    if not chunks:
        return 0.0, "none"
    scores = [float(c.get("score", 0.0)) for c in chunks]
    top = sorted(scores, reverse=True)[:10]
    mean = statistics.mean(top)
    n_docs = len({c["document_id"] for c in chunks})
    breadth_bonus = min(0.1, max(0, n_docs - 1) * 0.02)
    score = max(0.0, min(1.0, mean + breadth_bonus))
    if score < 0.4:
        band = "low"
    elif score < 0.65:
        band = "moderate"
    elif score < 0.85:
        band = "high"
    else:
        band = "very high"
    return score, band


def _build_evidence_table(chunks: list[dict]) -> list[dict]:
    """Deterministic evidence_table built from retrieved chunks.

    The LLM's own evidence_table tends to drop fields or invent titles, so we
    overwrite it. Each entry exposes enough for the UI to render a citation
    chip + an inline quote + a link to the source document.
    """
    table: list[dict] = []
    for c in chunks:
        text = (c.get("text_content") or "").strip()
        table.append(
            {
                "chunk_id": c["chunk_id"],
                "document_id": c.get("document_id"),
                "document_title": c.get("document_title", "Untitled"),
                "key_point": text[:240],
                "text": text[:400],
                "score": float(c.get("score", 0.0)),
            }
        )
    return table


def _scrub_arguments(
    args: list[dict] | None,
    valid_ids: set[str],
) -> list[dict]:
    """Drop any argument whose citations don't reference real chunks."""
    out: list[dict] = []
    for arg in args or []:
        if not isinstance(arg, dict):
            continue
        cited = [
            cid
            for cid in (arg.get("evidence_chunk_ids") or [])
            if isinstance(cid, str) and cid in valid_ids
        ]
        if not cited:
            log.warning(
                "research.dropped_uncited_claim",
                claim=str(arg.get("claim", ""))[:80],
            )
            continue
        arg["evidence_chunk_ids"] = cited
        out.append(arg)
    return out


async def synthesize_brief(topic: str, chunks: list[dict]) -> ResearchBrief:
    """Build a ResearchBrief from retrieved evidence chunks.

    Uses Groq first; falls back to Ollama. Confidence is computed
    deterministically from chunk similarity scores, not from the LLM.

    Raises NoEvidenceError if the chunk list is empty — the caller should
    treat this as a user-facing failure, not a system error.
    """
    if not chunks:
        raise NoEvidenceError(
            "Your library has no documents matching this topic. "
            "Upload relevant material first, then re-run the brief."
        )

    confidence, band = _compute_confidence(chunks)
    valid_ids = {c["chunk_id"] for c in chunks}

    messages = [
        {"role": "system", "content": "You output only valid JSON. No markdown fences."},
        {"role": "user", "content": _build_synthesis_prompt(topic, chunks)},
    ]

    last_exc: Exception | None = None
    for client_factory, label in [(_groq_client, "groq"), (_ollama_client, "ollama")]:
        try:
            client = client_factory()
            raw = await _chat_completion(client, messages, provider=label, temperature=0.1)
            data: dict = _coerce_json(raw)
            data.setdefault("topic", topic)
            data["key_arguments"] = _scrub_arguments(
                data.get("key_arguments"), valid_ids
            )
            data["counterarguments"] = _scrub_arguments(
                data.get("counterarguments"), valid_ids
            )
            # Overwrite with deterministic table — the LLM cannot lie about it.
            data["evidence_table"] = _build_evidence_table(chunks)
            data["confidence"] = confidence
            data["evidence_band"] = band
            return ResearchBrief.model_validate(data)
        except Exception as exc:
            last_exc = exc
            log.warning("synthesize_brief.failed", provider=label, error=str(exc))

    # Both providers failed — return a minimal fallback brief.
    log.error("synthesize_brief.all_providers_failed", error=str(last_exc))
    return ResearchBrief(
        topic=topic,
        executive_summary="Synthesis failed — LLM providers unavailable. Evidence was retrieved successfully; try again shortly.",
        key_arguments=[],
        evidence_table=_build_evidence_table(chunks),
        counterarguments=[],
        knowledge_gaps=["Unable to synthesize arguments — LLM providers returned errors."],
        recommended_reading=[],
        confidence=confidence,
        evidence_band=band,
    )
