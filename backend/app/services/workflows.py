"""Workflow evaluation and action helpers — Phase 4 Track F.

Provides:
  - Password encryption/decryption using Fernet derived from JWT secret
  - evaluate_workflows(): match events to enabled workflows and enqueue actions
  - send_email_action(): SMTP delivery
  - fire_webhook_action(): signed HTTP POST with retry
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import smtplib
import time
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TYPE_CHECKING

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.models.workflow import EmailSettings

log = get_logger(__name__)


# ─── Encryption helpers ───────────────────────────────────────────────────────


def _get_fernet(jwt_secret: str) -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(jwt_secret.encode()).digest())
    return Fernet(key)


def encrypt_password(plaintext: str, jwt_secret: str) -> str:
    """Encrypt an SMTP password using a key derived from the JWT secret."""
    return _get_fernet(jwt_secret).encrypt(plaintext.encode()).decode()


def decrypt_password(ciphertext: str, jwt_secret: str) -> str:
    """Decrypt an SMTP password using a key derived from the JWT secret."""
    return _get_fernet(jwt_secret).decrypt(ciphertext.encode()).decode()


# ─── Condition evaluation ─────────────────────────────────────────────────────


def _check_conditions(conditions: dict, payload: dict) -> bool:
    """Return True if all conditions in the dict are satisfied by payload."""
    for key, value in conditions.items():
        if key == "topic_in":
            # Check overlap between value list and payload topic/tags
            allowed = set(value) if isinstance(value, list) else {value}
            topic = payload.get("topic")
            tags = payload.get("tags", [])
            candidates = set()
            if topic:
                candidates.add(topic)
            if isinstance(tags, list):
                candidates.update(tags)
            if not candidates.intersection(allowed):
                return False

        elif key == "confidence_gte":
            threshold = float(value)
            actual = float(payload.get("confidence", 1.0))
            if actual < threshold:
                return False

        elif key == "source_type_in":
            allowed = value if isinstance(value, list) else [value]
            src = payload.get("source_type")
            if src not in allowed:
                return False

        # Unknown condition keys are silently ignored (forward-compatible)

    return True


# ─── Workflow evaluation ──────────────────────────────────────────────────────


def evaluate_workflows(
    session: Session,
    event_type: str,
    event_payload: dict,
    user_id: uuid.UUID,
) -> list[uuid.UUID]:
    """Find matching enabled workflows and enqueue their actions.

    Returns a list of workflow UUIDs that matched.
    """
    from app.models.workflow import Workflow, WorkflowRun
    from app.workers.celery_app import celery_app

    rows = session.execute(
        select(Workflow).where(
            Workflow.user_id == user_id,
            Workflow.enabled.is_(True),
            Workflow.trigger_event == event_type,
        )
    ).scalars().all()

    matched: list[uuid.UUID] = []

    for workflow in rows:
        conditions = workflow.conditions or {}
        if not _check_conditions(conditions, event_payload):
            continue

        # Create a workflow_run row
        run = WorkflowRun(
            workflow_id=workflow.id,
            status="running",
        )
        session.add(run)
        session.flush()  # get run.id

        # Update workflow bookkeeping
        from datetime import datetime, timezone

        workflow.last_run_at = datetime.now(timezone.utc)
        workflow.run_count = (workflow.run_count or 0) + 1

        # Enqueue action task
        celery_app.send_task(
            "execute_workflow_action",
            args=[str(workflow.id), str(run.id), json.dumps(event_payload)],
            queue="default",
        )

        matched.append(workflow.id)

    session.commit()
    log.info(
        "evaluate_workflows.done",
        event_type=event_type,
        user_id=str(user_id),
        matched=len(matched),
    )
    return matched


# ─── Action helpers ────────────────────────────────────────────────────────────


def send_email_action(
    email_settings_row: "EmailSettings",
    subject: str,
    body: str,
    jwt_secret: str,
) -> bool:
    """Send an email via SMTP using the user's stored settings.

    Returns True on success, False on failure.
    """
    try:
        password = decrypt_password(email_settings_row.smtp_password_encrypted, jwt_secret)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = email_settings_row.from_address
        msg["To"] = email_settings_row.from_address  # send to self by default

        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(email_settings_row.smtp_host, email_settings_row.smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(email_settings_row.smtp_username, password)
            server.sendmail(
                email_settings_row.from_address,
                [email_settings_row.from_address],
                msg.as_string(),
            )

        log.info(
            "send_email_action.sent",
            smtp_host=email_settings_row.smtp_host,
            subject=subject,
        )
        return True

    except Exception:
        log.exception("send_email_action.failed", subject=subject)
        return False


def fire_webhook_action(url: str, payload: dict, secret: str) -> bool:
    """POST payload to a webhook URL with HMAC signature and exponential-backoff retry.

    Returns True on 2xx response, False on failure.
    """
    import httpx

    body_bytes = json.dumps(payload).encode()
    sig = hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-NexusMind-Signature": f"sha256={sig}",
    }

    delays = [1, 2, 4]  # exponential backoff between attempts
    for attempt in range(3):
        try:
            resp = httpx.post(url, content=body_bytes, headers=headers, timeout=10.0)
            if resp.is_success:
                log.info(
                    "fire_webhook_action.ok",
                    url=url,
                    status=resp.status_code,
                    attempt=attempt,
                )
                return True
            log.warning(
                "fire_webhook_action.non_2xx",
                url=url,
                status=resp.status_code,
                attempt=attempt,
            )
        except Exception:
            log.exception("fire_webhook_action.exception", url=url, attempt=attempt)

        if attempt < 2:
            time.sleep(delays[attempt])  # 1s, 2s between attempts

    log.error("fire_webhook_action.failed_all_attempts", url=url)
    return False
