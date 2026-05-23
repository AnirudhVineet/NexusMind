"""Track F — sanity tests that the public renderer doesn't leak user data."""
from __future__ import annotations

from app.services.publish import _strip_pii


def test_no_pii_keys_survive_strip_pass():
    sensitive_keys = ("user_id", "uploaded_by", "owner_id", "session_id", "ip", "email")
    raw = {k: "secret" for k in sensitive_keys}
    raw["safe_field"] = "ok"
    cleaned = _strip_pii(raw)
    for k in sensitive_keys:
        assert k not in cleaned
    assert cleaned["safe_field"] == "ok"


def test_nested_pii_is_stripped():
    raw = {
        "level_1": {
            "level_2": {
                "user_id": "leak",
                "kept": "yes",
            }
        }
    }
    cleaned = _strip_pii(raw)
    assert cleaned["level_1"]["level_2"] == {"kept": "yes"}


def test_pii_inside_lists_is_stripped():
    raw = [{"email": "x@y"}, {"value": 5}]
    cleaned = _strip_pii(raw)
    assert cleaned == [{}, {"value": 5}]
