"""Spaced-repetition flashcard endpoints — Phase 3.6.

POST   /api/cards/generate      — kick off LLM card generation for a document
GET    /api/cards               — list cards (optionally by document)
GET    /api/cards/due           — cards due today or earlier
GET    /api/cards/stats         — streak, mastery, due count
POST   /api/cards/{id}/review   — submit an SM-2 rating (0..3)
PATCH  /api/cards/{id}          — edit Q/A or suspend
DELETE /api/cards/{id}
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.exceptions import NotFoundError
from app.db.session import get_session
from app.models.document import Document
from app.models.flashcard import Flashcard, FlashcardReview
from app.models.user import User
from app.services.sm2 import CardState, apply_sm2

router = APIRouter(prefix="/api", tags=["cards"])


# ─── schemas ──────────────────────────────────────────────────────────────────

class CardOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID | None
    chunk_id: uuid.UUID | None
    question: str
    answer: str
    reps: int
    interval_days: int
    ease: float
    due_date: str
    suspended: bool
    created_at: str


class GenerateRequest(BaseModel):
    document_id: uuid.UUID


class GenerateResponse(BaseModel):
    status: str
    document_id: uuid.UUID


class ReviewRequest(BaseModel):
    rating: int = Field(ge=0, le=3)


class ReviewResult(BaseModel):
    id: uuid.UUID
    reps: int
    interval_days: int
    ease: float
    due_date: str


class CardUpdate(BaseModel):
    question: str | None = None
    answer: str | None = None
    suspended: bool | None = None


class CardStats(BaseModel):
    total: int
    due_today: int
    mastered: int
    suspended: int
    reviews_last_7_days: int
    streak_days: int


def _serialize(card: Flashcard) -> CardOut:
    return CardOut(
        id=card.id,
        document_id=card.document_id,
        chunk_id=card.chunk_id,
        question=card.question,
        answer=card.answer,
        reps=card.reps,
        interval_days=card.interval_days,
        ease=card.ease,
        due_date=card.due_date.isoformat(),
        suspended=card.suspended,
        created_at=card.created_at.isoformat(),
    )


async def _get_owned(
    card_id: uuid.UUID, user: User, session: AsyncSession
) -> Flashcard:
    card = (
        await session.execute(
            select(Flashcard).where(
                Flashcard.id == card_id, Flashcard.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if card is None:
        raise NotFoundError("Flashcard not found")
    return card


# ─── generate ─────────────────────────────────────────────────────────────────

@router.post(
    "/cards/generate",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=GenerateResponse,
)
async def generate_cards(
    body: GenerateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GenerateResponse:
    doc = (
        await session.execute(
            select(Document).where(
                Document.id == body.document_id,
                Document.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        raise NotFoundError("Document not found")

    from app.workers.cards import generate_cards_task

    generate_cards_task.apply_async(args=[str(body.document_id)])
    return GenerateResponse(status="queued", document_id=body.document_id)


# ─── list ─────────────────────────────────────────────────────────────────────

@router.get("/cards", response_model=list[CardOut])
async def list_cards(
    document_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[CardOut]:
    stmt = (
        select(Flashcard)
        .where(Flashcard.user_id == current_user.id)
        .order_by(Flashcard.created_at.desc())
    )
    if document_id is not None:
        stmt = stmt.where(Flashcard.document_id == document_id)
    cards = (await session.execute(stmt)).scalars().all()
    return [_serialize(c) for c in cards]


@router.get("/cards/due", response_model=list[CardOut])
async def due_cards(
    limit: int = Query(default=100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[CardOut]:
    today = date.today()
    cards = (
        await session.execute(
            select(Flashcard)
            .where(
                Flashcard.user_id == current_user.id,
                Flashcard.suspended.is_(False),
                Flashcard.due_date <= today,
            )
            .order_by(Flashcard.due_date.asc(), Flashcard.created_at.asc())
            .limit(limit)
        )
    ).scalars().all()
    return [_serialize(c) for c in cards]


@router.get("/cards/stats", response_model=CardStats)
async def card_stats(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CardStats:
    uid = current_user.id
    today = date.today()

    total = (
        await session.execute(
            select(func.count(Flashcard.id)).where(Flashcard.user_id == uid)
        )
    ).scalar_one()
    due_today = (
        await session.execute(
            select(func.count(Flashcard.id)).where(
                Flashcard.user_id == uid,
                Flashcard.suspended.is_(False),
                Flashcard.due_date <= today,
            )
        )
    ).scalar_one()
    mastered = (
        await session.execute(
            select(func.count(Flashcard.id)).where(
                Flashcard.user_id == uid, Flashcard.reps >= 3
            )
        )
    ).scalar_one()
    suspended = (
        await session.execute(
            select(func.count(Flashcard.id)).where(
                Flashcard.user_id == uid, Flashcard.suspended.is_(True)
            )
        )
    ).scalar_one()

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    reviews_week = (
        await session.execute(
            select(func.count(FlashcardReview.id))
            .join(Flashcard, Flashcard.id == FlashcardReview.card_id)
            .where(
                Flashcard.user_id == uid,
                FlashcardReview.reviewed_at >= week_ago,
            )
        )
    ).scalar_one()

    # streak — consecutive days ending today (today may still be pending)
    review_days = (
        await session.execute(
            select(func.date(FlashcardReview.reviewed_at))
            .join(Flashcard, Flashcard.id == FlashcardReview.card_id)
            .where(Flashcard.user_id == uid)
            .distinct()
        )
    ).scalars().all()
    day_set = {d if isinstance(d, date) else date.fromisoformat(str(d)) for d in review_days}

    streak = 0
    cursor = today
    if cursor not in day_set:
        cursor = today - timedelta(days=1)
    while cursor in day_set:
        streak += 1
        cursor -= timedelta(days=1)

    return CardStats(
        total=int(total),
        due_today=int(due_today),
        mastered=int(mastered),
        suspended=int(suspended),
        reviews_last_7_days=int(reviews_week),
        streak_days=streak,
    )


# ─── review ───────────────────────────────────────────────────────────────────

@router.post("/cards/{card_id}/review", response_model=ReviewResult)
async def review_card(
    card_id: uuid.UUID,
    body: ReviewRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ReviewResult:
    card = await _get_owned(card_id, current_user, session)

    next_state = apply_sm2(
        CardState(
            reps=card.reps,
            interval_days=card.interval_days,
            ease=card.ease,
            due_date=card.due_date,
        ),
        body.rating,
    )
    card.reps = next_state.reps
    card.interval_days = next_state.interval_days
    card.ease = next_state.ease
    card.due_date = next_state.due_date

    session.add(FlashcardReview(card_id=card.id, rating=body.rating))
    await session.commit()
    await session.refresh(card)

    return ReviewResult(
        id=card.id,
        reps=card.reps,
        interval_days=card.interval_days,
        ease=card.ease,
        due_date=card.due_date.isoformat(),
    )


# ─── update / delete ──────────────────────────────────────────────────────────

@router.patch("/cards/{card_id}", response_model=CardOut)
async def update_card(
    card_id: uuid.UUID,
    body: CardUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CardOut:
    card = await _get_owned(card_id, current_user, session)
    if body.question is not None:
        card.question = body.question.strip()[:1000]
    if body.answer is not None:
        card.answer = body.answer.strip()[:2000]
    if body.suspended is not None:
        card.suspended = body.suspended
    await session.commit()
    await session.refresh(card)
    return _serialize(card)


@router.delete(
    "/cards/{card_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_card(
    card_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    card = await _get_owned(card_id, current_user, session)
    await session.delete(card)
    await session.commit()
