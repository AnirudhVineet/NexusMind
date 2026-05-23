"""Tests for workflow actions — Phase 4 Track F.

Covers: send_email_action with mocked SMTP, fire_webhook_action with mocked httpx.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.workflows import (
    decrypt_password,
    encrypt_password,
    fire_webhook_action,
    send_email_action,
)


# ---------------------------------------------------------------------------
# Encryption helpers
# ---------------------------------------------------------------------------

class TestPasswordEncryption:
    """Test Fernet encryption/decryption of SMTP passwords."""

    def test_roundtrip(self):
        secret = "my-jwt-secret"
        plaintext = "my-smtp-password-123"
        encrypted = encrypt_password(plaintext, secret)
        assert encrypted != plaintext
        decrypted = decrypt_password(encrypted, secret)
        assert decrypted == plaintext

    def test_different_secrets_fail(self):
        encrypted = encrypt_password("password", "secret1")
        with pytest.raises(Exception):
            decrypt_password(encrypted, "secret2")

    def test_empty_password(self):
        secret = "test"
        enc = encrypt_password("", secret)
        assert decrypt_password(enc, secret) == ""


# ---------------------------------------------------------------------------
# send_email_action
# ---------------------------------------------------------------------------

class TestSendEmailAction:
    """Test email sending with mocked SMTP."""

    def _email_settings(self) -> SimpleNamespace:
        return SimpleNamespace(
            smtp_host="smtp.gmail.com",
            smtp_port=587,
            smtp_username="user@gmail.com",
            smtp_password_encrypted=encrypt_password("pass", "jwt-secret"),
            from_address="user@gmail.com",
        )

    @patch("app.services.workflows.smtplib.SMTP")
    def test_successful_send(self, mock_smtp_cls):
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = send_email_action(
            self._email_settings(),
            subject="Test Subject",
            body="Test body",
            jwt_secret="jwt-secret",
        )
        assert result is True

    @patch("app.services.workflows.smtplib.SMTP")
    def test_smtp_failure_returns_false(self, mock_smtp_cls):
        mock_smtp_cls.side_effect = Exception("Connection refused")

        result = send_email_action(
            self._email_settings(),
            subject="Test",
            body="Body",
            jwt_secret="jwt-secret",
        )
        assert result is False


# ---------------------------------------------------------------------------
# fire_webhook_action
# ---------------------------------------------------------------------------

class TestFireWebhookAction:
    """Test webhook firing with mocked httpx."""

    @patch("app.services.workflows.httpx.post")
    @patch("app.services.workflows.time.sleep")
    def test_successful_webhook(self, mock_sleep, mock_post):
        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        result = fire_webhook_action(
            url="https://example.com/hook",
            payload={"event": "test"},
            secret="webhook-secret",
        )
        assert result is True
        mock_post.assert_called_once()

    @patch("app.services.workflows.httpx.post")
    @patch("app.services.workflows.time.sleep")
    def test_retry_on_failure(self, mock_sleep, mock_post):
        mock_fail = MagicMock()
        mock_fail.is_success = False
        mock_fail.status_code = 500

        mock_ok = MagicMock()
        mock_ok.is_success = True
        mock_ok.status_code = 200

        mock_post.side_effect = [mock_fail, mock_ok]

        result = fire_webhook_action(
            url="https://example.com/hook",
            payload={"event": "test"},
            secret="secret",
        )
        assert result is True
        assert mock_post.call_count == 2

    @patch("app.services.workflows.httpx.post")
    @patch("app.services.workflows.time.sleep")
    def test_all_retries_fail(self, mock_sleep, mock_post):
        mock_post.side_effect = Exception("network error")

        result = fire_webhook_action(
            url="https://example.com/hook",
            payload={},
            secret="secret",
        )
        assert result is False
        assert mock_post.call_count == 3
