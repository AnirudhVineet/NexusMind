"""Conversation history endpoints — Phase 3.2."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.exceptions import NotFoundError
from app.db.session import get_session
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User

router = APIRouter(prefix="/api", tags=["conversations"])


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    citations: list | None
    confidence_score: float | None
    created_at: str

    model_config = {"from_attributes": True}


class ConversationSummary(BaseModel):
    id: uuid.UUID
    title: str | None
    created_at: str
    message_count: int


class ConversationDetail(BaseModel):
    id: uuid.UUID
    title: str | None
    created_at: str
    messages: list[MessageOut]


class RenameRequest(BaseModel):
    title: str


@router.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ConversationSummary]:
    offset = (page - 1) * page_size

    # Subquery: message count per conversation
    msg_count_sq = (
        select(
            Message.conversation_id,
            func.count(Message.id).label("cnt"),
        )
        .group_by(Message.conversation_id)
        .subquery()
    )

    rows = (
        await session.execute(
            select(Conversation, func.coalesce(msg_count_sq.c.cnt, 0).label("msg_cnt"))
            .outerjoin(msg_count_sq, msg_count_sq.c.conversation_id == Conversation.id)
            .where(Conversation.user_id == current_user.id)
            .order_by(Conversation.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
    ).all()

    return [
        ConversationSummary(
            id=conv.id,
            title=conv.title,
            created_at=conv.created_at.isoformat(),
            message_count=int(cnt),
        )
        for conv, cnt in rows
    ]


@router.get("/conversations/{conv_id}", response_model=ConversationDetail)
async def get_conversation(
    conv_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ConversationDetail:
    conv = (
        await session.execute(
            select(Conversation).where(
                Conversation.id == conv_id,
                Conversation.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if conv is None:
        raise NotFoundError("Conversation not found")

    messages = (
        await session.execute(
            select(Message)
            .where(Message.conversation_id == conv_id)
            .order_by(Message.created_at.asc())
        )
    ).scalars().all()

    return ConversationDetail(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at.isoformat(),
        messages=[
            MessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                citations=m.citations,
                confidence_score=m.confidence_score,
                created_at=m.created_at.isoformat(),
            )
            for m in messages
        ],
    )


@router.patch("/conversations/{conv_id}", response_model=ConversationDetail)
async def rename_conversation(
    conv_id: uuid.UUID,
    body: RenameRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ConversationDetail:
    conv = (
        await session.execute(
            select(Conversation).where(
                Conversation.id == conv_id,
                Conversation.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if conv is None:
        raise NotFoundError("Conversation not found")

    conv.title = body.title.strip()[:200]
    await session.commit()
    await session.refresh(conv)
    return await get_conversation(conv_id, current_user, session)


@router.delete("/conversations/{conv_id}", status_code=204, response_model=None)
async def delete_conversation(
    conv_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    conv = (
        await session.execute(
            select(Conversation).where(
                Conversation.id == conv_id,
                Conversation.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if conv is None:
        raise NotFoundError("Conversation not found")
    await session.delete(conv)
    await session.commit()
