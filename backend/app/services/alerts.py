"""Semantic Alerts service functions.

Check functions run after document ingestion to evaluate user-configured
alert rules and create notifications as needed.

(The `interest_match` and `contradiction` alert types were removed
alongside the Memory and Conflicts features. Existing AlertRule rows
of those types remain in the DB but are silently ignored — no worker
queries them. The remaining alert types are `topic_keyword` and
`entity_mention`.)
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import AlertRule, Notification
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.entity import ChunkEntity


# ─── notification creator ─────────────────────────────────────────────────────

async def _create_notification(
    session: AsyncSession,
    user_id: uuid.UUID,
    source_alert_id: uuid.UUID | None,
    title: str,
    body: str,
    link: str,
    metadata: dict[str, Any] | None = None,
) -> uuid.UUID:
    """Insert a Notification row and return its id."""
    notif = Notification(
        user_id=user_id,
        source_alert_id=source_alert_id,
        title=title,
        body=body,
        link=link,
        metadata_=metadata or {},
    )
    session.add(notif)
    await session.flush()
    return notif.id


# ─── topic_keyword ────────────────────────────────────────────────────────────

async def check_keyword_match(
    document_id: uuid.UUID, session: AsyncSession
) -> list[uuid.UUID]:
    """Create notifications for topic_keyword alert rules matching this document's content."""
    doc = (
        await session.execute(select(Document).where(Document.id == document_id))
    ).scalar_one_or_none()
    if doc is None:
        return []

    rules = (
        await session.execute(
            select(AlertRule).where(
                AlertRule.user_id == doc.user_id,
                AlertRule.alert_type == "topic_keyword",
                AlertRule.enabled.is_(True),
            )
        )
    ).scalars().all()
    if not rules:
        return []

    # Build searchable text: title + first 2000 chars of chunk content
    chunks = (
        await session.execute(
            select(Chunk.text_content)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.chunk_index)
        )
    ).scalars().all()

    chunk_text = " ".join(chunks)[:2000]
    searchable = (doc.filename + " " + chunk_text).lower()

    created: list[uuid.UUID] = []
    for rule in rules:
        keywords: list[str] = rule.config.get("keywords", [])
        matched_keywords = [kw for kw in keywords if kw.lower() in searchable]
        if matched_keywords:
            notif_id = await _create_notification(
                session=session,
                user_id=doc.user_id,
                source_alert_id=rule.id,
                title=f"Keyword match in '{doc.filename}'",
                body=(
                    f"Document '{doc.filename}' contains keyword(s): "
                    f"{', '.join(matched_keywords)}."
                ),
                link=f"/documents/{document_id}",
                metadata={
                    "document_id": str(document_id),
                    "matched_keywords": matched_keywords,
                    "rule_name": rule.name,
                },
            )
            created.append(notif_id)

    if created:
        await session.commit()
    return created


# ─── entity_mention ───────────────────────────────────────────────────────────

async def check_entity_mention(
    document_id: uuid.UUID, session: AsyncSession
) -> list[uuid.UUID]:
    """Create notifications for entity_mention alert rules matching this document's entities."""
    doc = (
        await session.execute(select(Document).where(Document.id == document_id))
    ).scalar_one_or_none()
    if doc is None:
        return []

    rules = (
        await session.execute(
            select(AlertRule).where(
                AlertRule.user_id == doc.user_id,
                AlertRule.alert_type == "entity_mention",
                AlertRule.enabled.is_(True),
            )
        )
    ).scalars().all()
    if not rules:
        return []

    # Find all entities mentioned in this document via chunk_entities
    entity_id_rows = (
        await session.execute(
            select(ChunkEntity.entity_id)
            .join(Chunk, ChunkEntity.chunk_id == Chunk.id)
            .where(Chunk.document_id == document_id)
            .distinct()
        )
    ).scalars().all()
    doc_entity_ids: set[str] = {str(eid) for eid in entity_id_rows}

    if not doc_entity_ids:
        return []

    created: list[uuid.UUID] = []
    for rule in rules:
        watched: list[str] = [str(eid) for eid in rule.config.get("entity_ids", [])]
        matched = [eid for eid in watched if eid in doc_entity_ids]
        if matched:
            notif_id = await _create_notification(
                session=session,
                user_id=doc.user_id,
                source_alert_id=rule.id,
                title=f"Watched entity mentioned in '{doc.filename}'",
                body=(
                    f"Document '{doc.filename}' mentions "
                    f"{len(matched)} watched entit{'y' if len(matched) == 1 else 'ies'}."
                ),
                link=f"/documents/{document_id}",
                metadata={
                    "document_id": str(document_id),
                    "matched_entity_ids": matched,
                    "rule_name": rule.name,
                },
            )
            created.append(notif_id)

    if created:
        await session.commit()
    return created
