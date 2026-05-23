"""Track A — reel-job quota gate behaviour."""
from __future__ import annotations

import importlib

import pytest

from app.services.media import quota_check


class _FakeRedis:
    def __init__(self):
        self.store: dict[str, int] = {}

    def from_url(self, *_args, **_kwargs):
        return self

    def incr(self, key):
        self.store[key] = self.store.get(key, 0) + 1
        return self.store[key]

    def decr(self, key):
        if key in self.store:
            self.store[key] = max(0, self.store[key] - 1)
        return self.store.get(key, 0)

    def expire(self, *_args, **_kwargs):
        pass

    def get(self, key):
        v = self.store.get(key)
        return str(v).encode() if v is not None else None


def test_check_and_increment_allows_under_cap(monkeypatch):
    fake = _FakeRedis()
    import sys
    fake_module = type(sys)("redis")  # stub the redis module
    fake_module.Redis = fake  # type: ignore[attr-defined]
    monkeypatch.setitem(__import__("sys").modules, "redis", fake_module)

    ok, current, cap = quota_check.check_and_increment("user-1", "reel")
    assert ok is True
    assert current == 1
    assert cap > 0


def test_check_and_increment_denies_over_cap(monkeypatch):
    fake = _FakeRedis()
    import sys
    fake_module = type(sys)("redis")
    fake_module.Redis = fake  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "redis", fake_module)

    # Slam past the reel daily cap (10 by default)
    last_ok = True
    for _ in range(15):
        ok, _c, _cap = quota_check.check_and_increment("user-2", "reel")
        last_ok = ok
    assert last_ok is False


def test_fail_open_when_redis_missing(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "redis", None)
    ok, current, cap = quota_check.check_and_increment("user-3", "reel")
    # Without redis we don't block work
    assert ok is True
    assert current == 0
    assert cap > 0


def test_current_usage_returns_cap_even_without_redis(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "redis", None)
    current, cap = quota_check.current_usage("user-4", "narration")
    assert current == 0
    assert cap > 0
