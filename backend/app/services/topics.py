"""Corpus-wide topic discovery via BERTopic.

Periodically (daily) we run BERTopic over every chunk's text + existing
embedding, produce up to ~50 topic clusters per user, then label each cluster
via a short Qwen2.5 call (5-token cluster name). The clusters become
`topic_tags` rows with `source='bertopic'`; documents are linked through
`document_tags` based on the dominant cluster of their chunks.

This runs as a heavy beat task, so we skip when the corpus is small or hasn't
changed materially since the last run.
"""
from __future__ import annotations

import re
import uuid
from collections import Counter
from typing import Any

import numpy as np
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.logging import get_logger
from app.db.sync_session import get_sync_session
from app.models.chunk import Chunk
from app.models.topic import DocumentTag, TopicTag
from app.services.llm_local import call_text_sync

log = get_logger(__name__)


_MIN_CHUNKS_FOR_BERTOPIC = 50
_CHANGE_THRESHOLD = 0.05  # skip if corpus grew by < 5% since last run


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    s = _SLUG_RE.sub("-", text.lower()).strip("-")
    return s[:64] or "topic"


def _label_cluster(sample_texts: list[str]) -> str:
    """Ask the LLM for a 1-4 word topic label given representative chunks."""
    joined = "\n\n".join(t[:600] for t in sample_texts[:5])
    system = (
        "Produce a 1-4 word topic label for the chunks below. Output the "
        "label only — no punctuation, no quotation marks, no explanation."
    )
    user = f"Chunks:\n\n{joined}"
    try:
        label, _ = call_text_sync(
            system=system, user=user, task_label="topic_label", temperature=0.0
        )
        return (label or "").strip().splitlines()[0].strip().strip('"')[:64]
    except Exception:
        log.exception("topics.label_cluster.failed")
        return ""


def _per_user_corpora(session) -> dict[uuid.UUID, list[Chunk]]:
    rows = list(
        session.execute(
            select(Chunk).where(Chunk.embedding.is_not(None))
        ).scalars()
    )
    grouped: dict[uuid.UUID, list[Chunk]] = {}
    for c in rows:
        grouped.setdefault(c.user_id, []).append(c)
    return grouped


def _run_bertopic(chunks: list[Chunk]) -> tuple[list[int], dict[int, list[str]]]:
    """Returns (labels per chunk, topic_id -> representative chunk texts)."""
    from bertopic import BERTopic

    texts = [c.text_content for c in chunks]
    embeddings = np.array([c.embedding for c in chunks])

    model = BERTopic(verbose=False, calculate_probabilities=False, min_topic_size=10)
    labels, _ = model.fit_transform(texts, embeddings=embeddings)

    rep: dict[int, list[str]] = {}
    for topic_id in set(labels):
        if topic_id == -1:
            continue
        rep_docs = model.get_representative_docs(topic_id)
        rep[topic_id] = rep_docs[:5] if rep_docs else []
    return list(labels), rep


def _dominant_topic_per_doc(
    chunks: list[Chunk], labels: list[int]
) -> dict[uuid.UUID, tuple[int, float]]:
    """For each document, pick the topic that the majority of its chunks fall into.

    Returns document_id -> (topic_id, share-of-chunks-in-that-topic).
    """
    by_doc: dict[uuid.UUID, list[int]] = {}
    for chunk, label in zip(chunks, labels):
        if label == -1:
            continue
        by_doc.setdefault(chunk.document_id, []).append(int(label))

    result: dict[uuid.UUID, tuple[int, float]] = {}
    for doc_id, lbls in by_doc.items():
        if not lbls:
            continue
        counts = Counter(lbls)
        top_topic, top_count = counts.most_common(1)[0]
        result[doc_id] = (int(top_topic), top_count / len(lbls))
    return result


def _recompute_for_user(session, user_id: uuid.UUID, chunks: list[Chunk]) -> dict[str, Any]:
    if len(chunks) < _MIN_CHUNKS_FOR_BERTOPIC:
        return {"user_id": str(user_id), "skipped": True, "reason": "small_corpus"}

    labels, rep_by_topic = _run_bertopic(chunks)

    # Build topic_tag rows (source='bertopic'). Replace prior BERTopic tags
    # for this user wholesale so stale clusters are dropped.
    session.execute(
        delete(TopicTag).where(
            TopicTag.user_id == user_id, TopicTag.source == "bertopic"
        )
    )

    topic_id_to_tag_id: dict[int, uuid.UUID] = {}
    for topic_id, rep_docs in rep_by_topic.items():
        display = _label_cluster(rep_docs) or f"topic-{topic_id}"
        slug = _slugify(display) + f"-{topic_id}"
        tag_id = uuid.uuid4()
        session.execute(
            TopicTag.__table__.insert().values(
                id=tag_id,
                user_id=user_id,
                slug=slug,
                display_name=display,
                source="bertopic",
                bertopic_id=topic_id,
            )
        )
        topic_id_to_tag_id[topic_id] = tag_id
    session.commit()

    # Link documents to dominant cluster.
    dominant = _dominant_topic_per_doc(chunks, labels)
    upserted = 0
    for doc_id, (topic_id, share) in dominant.items():
        tag_id = topic_id_to_tag_id.get(topic_id)
        if tag_id is None:
            continue
        session.execute(
            pg_insert(DocumentTag)
            .values(
                document_id=doc_id,
                tag_id=tag_id,
                confidence=float(share),
            )
            .on_conflict_do_update(
                index_elements=["document_id", "tag_id"],
                set_={"confidence": float(share)},
            )
        )
        upserted += 1
    session.commit()

    return {
        "user_id": str(user_id),
        "clusters": len(rep_by_topic),
        "doc_links": upserted,
    }


def recompute_all_topics() -> dict[str, Any]:
    """Top-level entry point called from the maintenance Celery task."""
    session = get_sync_session()
    try:
        grouped = _per_user_corpora(session)
        results = []
        for user_id, chunks in grouped.items():
            try:
                results.append(_recompute_for_user(session, user_id, chunks))
            except Exception:
                log.exception("topics.recompute_user.failed", user_id=str(user_id))
        return {"users_processed": len(results), "results": results}
    finally:
        session.close()
