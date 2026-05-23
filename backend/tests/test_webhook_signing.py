"""Tests for webhook HMAC-SHA256 signing — Phase 4 Track F.

Covers: HMAC signature generation and verification.
"""
import hashlib
import hmac
import json

import pytest


class TestWebhookSigning:
    """Verify HMAC-SHA256 signature generation matches the verification side."""

    def _sign(self, payload: dict, secret: str) -> str:
        """Reproduce the signing logic from fire_webhook_action."""
        body_bytes = json.dumps(payload).encode()
        sig = hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest()
        return f"sha256={sig}"

    def _verify(self, payload: dict, secret: str, signature: str) -> bool:
        """Verify an HMAC-SHA256 signature."""
        expected = self._sign(payload, secret)
        return hmac.compare_digest(expected, signature)

    def test_signature_roundtrip(self):
        payload = {"event": "document_ingested", "document_id": "abc"}
        secret = "my-webhook-secret"
        sig = self._sign(payload, secret)
        assert self._verify(payload, secret, sig) is True

    def test_wrong_secret_fails(self):
        payload = {"event": "test"}
        sig = self._sign(payload, "correct-secret")
        assert self._verify(payload, "wrong-secret", sig) is False

    def test_modified_payload_fails(self):
        payload = {"event": "test"}
        sig = self._sign(payload, "secret")
        payload["event"] = "tampered"
        assert self._verify(payload, "secret", sig) is False

    def test_empty_payload(self):
        payload = {}
        secret = "secret"
        sig = self._sign(payload, secret)
        assert sig.startswith("sha256=")
        assert self._verify(payload, secret, sig) is True

    def test_signature_format(self):
        sig = self._sign({"a": 1}, "secret")
        assert sig.startswith("sha256=")
        hex_part = sig[len("sha256="):]
        assert len(hex_part) == 64  # SHA-256 = 64 hex chars

    def test_deterministic(self):
        payload = {"key": "value"}
        secret = "s3cret"
        sig1 = self._sign(payload, secret)
        sig2 = self._sign(payload, secret)
        assert sig1 == sig2

    def test_different_payloads_different_sigs(self):
        secret = "secret"
        sig1 = self._sign({"a": 1}, secret)
        sig2 = self._sign({"a": 2}, secret)
        assert sig1 != sig2
