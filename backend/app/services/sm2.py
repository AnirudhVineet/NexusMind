"""SM-2 spaced-repetition scheduler (Phase 3.6).

Pure, dependency-free implementation. Ratings use a 4-button scale:

    0 = again   1 = hard   2 = good   3 = easy

mapped onto SM-2's 0..5 quality scale as ``q = rating + 2``. A rating of
``again`` resets the card's progress; the ease factor is left untouched on
a lapse and floored at 1.3 otherwise.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

MIN_EASE = 1.3
DEFAULT_EASE = 2.5


@dataclass(frozen=True)
class CardState:
    reps: int
    interval_days: int
    ease: float
    due_date: date


def apply_sm2(state: CardState, rating: int, today: date | None = None) -> CardState:
    """Return the next card state after grading a review.

    `rating` must be in 0..3. `today` defaults to the current date.
    """
    if rating < 0 or rating > 3:
        raise ValueError("rating must be between 0 and 3")
    today = today or date.today()

    q = rating + 2  # 4-button scale -> SM-2 quality 2..5

    # Lapse: rating 0 ("again"). Reset progress, keep ease.
    if q < 3:
        return CardState(
            reps=0,
            interval_days=1,
            ease=state.ease,
            due_date=today + timedelta(days=1),
        )

    if state.reps == 0:
        interval = 1
    elif state.reps == 1:
        interval = 6
    else:
        interval = round(state.interval_days * state.ease)

    interval = max(1, interval)
    ease = max(MIN_EASE, state.ease + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)))

    return CardState(
        reps=state.reps + 1,
        interval_days=interval,
        ease=ease,
        due_date=today + timedelta(days=interval),
    )
