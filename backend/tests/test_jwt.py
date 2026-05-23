import time
import uuid

import pytest

from app.auth.jwt import create_access_token, decode_token
from app.core.exceptions import AuthError


def test_token_roundtrip():
    uid = uuid.uuid4()
    token, expires_in = create_access_token(uid, "user@example.com")
    assert expires_in > 0

    payload = decode_token(token)
    assert payload["sub"] == str(uid)
    assert payload["email"] == "user@example.com"
    assert payload["exp"] > payload["iat"]


def test_invalid_token_raises():
    with pytest.raises(AuthError):
        decode_token("not-a-token")


def test_expired_token_rejected(monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "jwt_expiry_seconds", -1)
    token, _ = create_access_token(uuid.uuid4(), "x@y.com")
    time.sleep(0.01)
    with pytest.raises(AuthError):
        decode_token(token)
