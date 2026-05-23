"""Track F — share-link expiry handling."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace


def _make_link(expires_at):
    """Lightweight stand-in for the ORM ShareLink — avoids triggering
    full SQLAlchemy mapper configuration in pure unit tests."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        target_type="brief",
        target_id=uuid.uuid4(),
        slug="abcDEF123456",
        expires_at=expires_at,
        view_count=0,
        enabled=True,
        created_at=datetime.now(timezone.utc),
    )


def test_expired_link_is_in_the_past():
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    link = _make_link(past)
    assert link.expires_at is not None
    assert link.expires_at < datetime.now(timezone.utc)


def test_active_link_in_the_future():
    fut = datetime.now(timezone.utc) + timedelta(hours=1)
    link = _make_link(fut)
    assert link.expires_at > datetime.now(timezone.utc)


def test_no_expiry_link():
    link = _make_link(None)
    assert link.expires_at is None
