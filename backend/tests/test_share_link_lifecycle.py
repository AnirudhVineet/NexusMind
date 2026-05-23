"""Track F — share link lifecycle: slug generation, password hashing, expiry."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from app.services import publish


def test_generate_slug_shape():
    slug = publish.generate_slug()
    assert len(slug) == publish.SLUG_LEN
    assert re.match(r"^[A-Za-z0-9_-]+$", slug)


def test_slug_uniqueness_over_100_calls():
    seen = {publish.generate_slug() for _ in range(100)}
    assert len(seen) == 100  # extremely unlikely to collide


def test_password_hash_roundtrip():
    h = publish.hash_password("hunter2")
    assert publish.verify_password("hunter2", h) is True
    assert publish.verify_password("wrong", h) is False


def test_password_hash_includes_salt():
    a = publish.hash_password("same")
    b = publish.hash_password("same")
    # Different salts → different hashes
    assert a != b
    # Both still verify
    assert publish.verify_password("same", a)
    assert publish.verify_password("same", b)


def test_strip_pii_drops_sensitive_keys():
    raw = {
        "topic": "x",
        "user_id": "uuid-here",
        "email": "leak@example.com",
        "nested": {"owner_id": "uuid", "ok": True},
        "list": [{"session_id": "sid"}, {"safe": 1}],
    }
    cleaned = publish._strip_pii(raw)
    assert "user_id" not in cleaned
    assert "email" not in cleaned
    assert cleaned["nested"] == {"ok": True}
    assert cleaned["list"] == [{}, {"safe": 1}]
