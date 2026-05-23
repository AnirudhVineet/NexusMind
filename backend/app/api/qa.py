import json
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.db.session import get_session
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.message import Message
from app.models.user import User
from app.schemas.qa import Citation, QARequest, QAResponse, SearchFiltersSchema
from app.services.embedding import get_embedding_service
from app.services.llm import (
    Excerpt,
    call_llm,
    extract_citation_indices,
    stream_llm,
)
from app.services.retrieval import (
    RetrievalHit,
    SearchFilters,
    hybrid_search,
)

log = get_logger(__name__)

router = APIRouter(prefix="", tags=["qa"])

NO_SOURCE_ANSWER = (
    "I do not have enough information in my knowledge base to answer this."
)


def _snippet(text: str, n: int = 200) -> str:
    text = (text or "").strip()
    if len(text) <= n:
        return text
    return text[:n].rstrip() + "…"


def _schema_to_filters(
    schema: SearchFiltersSchema | None,
    document_ids_override: list[uuid.UUID] | None = None,
) -> SearchFilters:
    if schema is None:
        return SearchFilters(document_ids=document_ids_override or [])
    doc_ids = schema.document_ids or document_ids_override or []
    return SearchFilters(
        source_type=schema.source_type,
        date_from=schema.date_from,
        date_to=schema.date_to,
        topic_tag=schema.topic_tag,
        min_credibility=schema.min_credibility,
        entity_id=schema.entity_id,
        document_ids=doc_ids,
    )


async def _verify_doc_ownership(
    session: AsyncSession, user_id: uuid.UUID, doc_ids: list[uuid.UUID]
) -> None:
    if not doc_ids:
        return
    rows = (
        await session.execute(
            select(Document.id).where(
                Document.user_id == user_id, Document.id.in_(doc_ids)
            )
        )
    ).scalars().all()
    if len(set(rows)) != len(set(doc_ids)):
        raise ValidationError("One or more document_ids do not belong to the user")


async def _get_or_create_conversation(
    session: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    question: str,
) -> Conversation:
    if conversation_id is not None:
        conv = (
            await session.execute(
                select(Conversation).where(
                    Conversation.id == conversation_id,
                    Conversation.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        if conv is None:
            raise NotFoundError("Conversation not found")
        return conv

    title = question.strip()[:80]
    conv = Conversation(user_id=user_id, title=title)
    session.add(conv)
    await session.flush()
    return conv


async def _load_conversation_history(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    max_turns: int = 6,
) -> list[dict]:
    """Return last N messages as [{"role": ..., "content": ...}]."""
    rows = (
        await session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(max_turns)
        )
    ).scalars().all()
    return [{"role": m.role, "content": m.content} for m in reversed(rows)]


def _build_excerpts(hits: list[RetrievalHit]) -> list[Excerpt]:
    return [
        Excerpt(
            index=i + 1,
            document_title=h.document_title,
            page_number=h.page_number,
            section=h.section,
            text=h.text,
        )
        for i, h in enumerate(hits)
    ]


def _resolve_citations(
    answer: str, hits: list[RetrievalHit]
) -> tuple[list[Citation], float]:
    raw_indices = extract_citation_indices(answer)
    valid_indices: list[int] = []
    seen: set[int] = set()
    for idx in raw_indices:
        if 1 <= idx <= len(hits) and idx not in seen:
            valid_indices.append(idx)
            seen.add(idx)
        elif idx not in seen:
            log.warning("qa.unknown_citation_marker", index=idx)
            seen.add(idx)

    citations: list[Citation] = []
    for idx in valid_indices:
        h = hits[idx - 1]
        citations.append(
            Citation(
                index=idx,
                chunk_id=h.chunk_id,
                document_title=h.document_title,
                page_number=h.page_number,
                section=h.section,
                snippet=_snippet(h.text),
            )
        )
    max_sim = max((h.similarity_score for h in hits), default=0.0)
    if citations:
        conf = round(
            sum(hits[c.index - 1].similarity_score for c in citations) / len(citations),
            4,
        )
    else:
        conf = round(max_sim, 4)
    return citations, conf


@router.post("/qa", response_model=QAResponse)
async def qa(
    body: QARequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> QAResponse:
    settings = get_settings()
    top_k = min(body.top_k or settings.search_top_k_default, 50)

    # Build filters (merge legacy document_ids into filters)
    filters = _schema_to_filters(body.filters, body.document_ids)
    if filters.document_ids:
        await _verify_doc_ownership(session, current_user.id, filters.document_ids)

    embedder = get_embedding_service()
    query_vec = await embedder.embed_query(body.question)

    hits = await hybrid_search(
        session=session,
        user_id=current_user.id,
        query=body.question,
        query_vec=query_vec,
        top_k=top_k,
        filters=filters,
    )

    max_sim = max((h.similarity_score for h in hits), default=0.0)

    conv = await _get_or_create_conversation(
        session, current_user.id, body.conversation_id, body.question
    )

    if not hits or max_sim < settings.qa_no_source_threshold:
        session.add_all(
            [
                Message(conversation_id=conv.id, role="user", content=body.question),
                Message(
                    conversation_id=conv.id,
                    role="assistant",
                    content=NO_SOURCE_ANSWER,
                    citations=[],
                    confidence_score=0.0,
                ),
            ]
        )
        await session.commit()
        return QAResponse(
            answer=NO_SOURCE_ANSWER,
            citations=[],
            confidence_score=0.0,
            no_source_found=True,
            conversation_id=conv.id,
        )

    # Load sliding-window conversation history
    history = await _load_conversation_history(session, conv.id)
    excerpts = _build_excerpts(hits)
    answer = await call_llm(body.question, excerpts, history=history)
    citations, confidence_score = _resolve_citations(answer, hits)

    cit_dicts = [c.model_dump(mode="json") for c in citations]
    session.add_all(
        [
            Message(conversation_id=conv.id, role="user", content=body.question),
            Message(
                conversation_id=conv.id,
                role="assistant",
                content=answer,
                citations=cit_dicts,
                confidence_score=confidence_score,
            ),
        ]
    )
    await session.commit()

    return QAResponse(
        answer=answer,
        citations=citations,
        confidence_score=confidence_score,
        no_source_found=False,
        conversation_id=conv.id,
    )


@router.post("/qa/stream")
async def qa_stream(
    body: QARequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Stream Q&A response via POST + ReadableStream (not EventSource)."""
    settings = get_settings()
    top_k = min(body.top_k or settings.search_top_k_default, 50)

    filters = _schema_to_filters(body.filters, body.document_ids)
    if filters.document_ids:
        await _verify_doc_ownership(session, current_user.id, filters.document_ids)

    embedder = get_embedding_service()
    query_vec = await embedder.embed_query(body.question)

    hits = await hybrid_search(
        session=session,
        user_id=current_user.id,
        query=body.question,
        query_vec=query_vec,
        top_k=top_k,
        filters=filters,
    )

    max_sim = max((h.similarity_score for h in hits), default=0.0)
    conv = await _get_or_create_conversation(
        session, current_user.id, body.conversation_id, body.question
    )
    # Persist user message immediately
    user_msg = Message(conversation_id=conv.id, role="user", content=body.question)
    session.add(user_msg)
    await session.flush()
    conv_id = conv.id
    await session.commit()

    async def generate() -> AsyncGenerator[bytes, None]:
        # Emit conversation_id first so the client can track it
        meta_payload = json.dumps({"conversation_id": str(conv_id)})
        yield f"event: metadata\ndata: {meta_payload}\n\n".encode()

        if not hits or max_sim < settings.qa_no_source_threshold:
            yield b"event: no_source\ndata: {}\n\n"
            # Persist no-source assistant message
            async with AsyncSessionLocal() as s2:
                s2.add(
                    Message(
                        conversation_id=conv_id,
                        role="assistant",
                        content=NO_SOURCE_ANSWER,
                        citations=[],
                        confidence_score=0.0,
                    )
                )
                await s2.commit()
            return

        history = []  # history already loaded before stream; pass empty to avoid re-load
        excerpts = _build_excerpts(hits)
        full_answer_parts: list[str] = []

        async for token in stream_llm(body.question, excerpts, history=history):
            full_answer_parts.append(token)
            payload = json.dumps({"t": token})
            yield f"event: token\ndata: {payload}\n\n".encode()

        full_answer = "".join(full_answer_parts)
        citations, confidence_score = _resolve_citations(full_answer, hits)
        cit_dicts = [c.model_dump(mode="json") for c in citations]

        cit_payload = json.dumps(
            [c.model_dump(mode="json") for c in citations]
        )
        yield f"event: citations\ndata: {cit_payload}\n\n".encode()
        yield b"event: done\ndata: {}\n\n"

        # Persist assistant message after stream
        from app.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as s2:
            s2.add(
                Message(
                    conversation_id=conv_id,
                    role="assistant",
                    content=full_answer,
                    citations=cit_dicts,
                    confidence_score=confidence_score,
                )
            )
            await s2.commit()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# Late import to avoid circular at module load
from app.db.session import AsyncSessionLocal  # noqa: E402
