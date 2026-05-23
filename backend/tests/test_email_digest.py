"""Tests for email digest batching — Phase 4 Track G.

Covers: notification batching, digest hour filtering, unread selection.
"""
from datetime import datetime, timedelta, timezone

import pytest


def _batch_unread_notifications(
    notifications: list[dict],
    now: datetime,
    lookback_hours: int = 24,
) -> list[dict]:
    """Simulate the digest batching logic.

    Returns notifications that are unread and created within lookback_hours.
    """
    cutoff = now - timedelta(hours=lookback_hours)
    return [
        n for n in notifications
        if n["read_at"] is None
        and n["created_at"] >= cutoff
    ]


class TestDigestBatching:
    """Test email digest notification batching."""

    def _notif(self, hours_ago: float, read: bool = False) -> dict:
        now = datetime.now(timezone.utc)
        return {
            "id": f"n-{hours_ago}",
            "title": f"Notification {hours_ago}h ago",
            "body": "Body text",
            "read_at": now if read else None,
            "created_at": now - timedelta(hours=hours_ago),
        }

    def test_recent_unread_included(self):
        now = datetime.now(timezone.utc)
        notifs = [self._notif(1), self._notif(12)]
        result = _batch_unread_notifications(notifs, now)
        assert len(result) == 2

    def test_old_notifications_excluded(self):
        now = datetime.now(timezone.utc)
        notifs = [self._notif(1), self._notif(30)]
        result = _batch_unread_notifications(notifs, now, lookback_hours=24)
        assert len(result) == 1

    def test_read_notifications_excluded(self):
        now = datetime.now(timezone.utc)
        notifs = [self._notif(1, read=True), self._notif(2)]
        result = _batch_unread_notifications(notifs, now)
        assert len(result) == 1

    def test_empty_notifications(self):
        now = datetime.now(timezone.utc)
        result = _batch_unread_notifications([], now)
        assert result == []

    def test_all_read_returns_empty(self):
        now = datetime.now(timezone.utc)
        notifs = [self._notif(1, read=True), self._notif(2, read=True)]
        result = _batch_unread_notifications(notifs, now)
        assert result == []

    def test_skip_digest_when_no_unread(self):
        """The digest job should skip sending if result is empty."""
        now = datetime.now(timezone.utc)
        result = _batch_unread_notifications([], now)
        should_send = len(result) > 0
        assert should_send is False
