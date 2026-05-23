"""Track F — share-link password verification edge cases."""
from __future__ import annotations

from app.services.publish import hash_password, verify_password


def test_verify_password_handles_malformed_hash():
    assert verify_password("anything", "no-dollar-sign-here") is False
    assert verify_password("anything", "") is False


def test_verify_password_case_sensitive():
    h = hash_password("Hunter2")
    assert verify_password("Hunter2", h)
    assert not verify_password("hunter2", h)
    assert not verify_password("HUNTER2", h)


def test_long_password_supported():
    pwd = "x" * 128
    h = hash_password(pwd)
    assert verify_password(pwd, h)
