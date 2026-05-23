"""Tests for the SM-2 scheduler — pure function, no I/O."""
from datetime import date, timedelta

import pytest

from app.services.sm2 import DEFAULT_EASE, MIN_EASE, CardState, apply_sm2

TODAY = date(2026, 5, 17)


def _fresh() -> CardState:
    return CardState(reps=0, interval_days=0, ease=DEFAULT_EASE, due_date=TODAY)


def test_again_resets_progress():
    state = CardState(reps=5, interval_days=40, ease=2.6, due_date=TODAY)
    nxt = apply_sm2(state, rating=0, today=TODAY)
    assert nxt.reps == 0
    assert nxt.interval_days == 1
    assert nxt.due_date == TODAY + timedelta(days=1)
    # ease is left untouched on a lapse
    assert nxt.ease == 2.6


def test_hard_lowers_ease_first_review():
    nxt = apply_sm2(_fresh(), rating=1, today=TODAY)
    assert nxt.reps == 1
    assert nxt.interval_days == 1
    assert nxt.due_date == TODAY + timedelta(days=1)
    assert nxt.ease == pytest.approx(DEFAULT_EASE - 0.14)


def test_good_keeps_ease_first_review():
    nxt = apply_sm2(_fresh(), rating=2, today=TODAY)
    assert nxt.reps == 1
    assert nxt.interval_days == 1
    assert nxt.ease == pytest.approx(DEFAULT_EASE)


def test_easy_raises_ease():
    nxt = apply_sm2(_fresh(), rating=3, today=TODAY)
    assert nxt.reps == 1
    assert nxt.interval_days == 1
    assert nxt.ease == pytest.approx(DEFAULT_EASE + 0.1)


def test_second_review_interval_is_six():
    after_first = apply_sm2(_fresh(), rating=2, today=TODAY)
    after_second = apply_sm2(after_first, rating=2, today=TODAY)
    assert after_second.reps == 2
    assert after_second.interval_days == 6
    assert after_second.due_date == TODAY + timedelta(days=6)


def test_third_review_scales_by_ease():
    state = CardState(reps=2, interval_days=6, ease=2.5, due_date=TODAY)
    nxt = apply_sm2(state, rating=2, today=TODAY)
    assert nxt.interval_days == round(6 * 2.5)  # 15
    assert nxt.due_date == TODAY + timedelta(days=15)


def test_ease_never_drops_below_minimum():
    state = CardState(reps=10, interval_days=100, ease=MIN_EASE, due_date=TODAY)
    for _ in range(20):
        state = apply_sm2(state, rating=1, today=TODAY)
    assert state.ease >= MIN_EASE


def test_invalid_rating_raises():
    with pytest.raises(ValueError):
        apply_sm2(_fresh(), rating=4, today=TODAY)
    with pytest.raises(ValueError):
        apply_sm2(_fresh(), rating=-1, today=TODAY)


def test_default_today_does_not_crash():
    nxt = apply_sm2(_fresh(), rating=2)
    assert nxt.due_date >= date.today()
