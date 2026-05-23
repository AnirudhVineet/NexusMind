"""Semantic Alerts Celery workers.

run_all_alert_checks_task     — evaluate all per-document alert rules after ingestion
send_email_digest_task        — beat task: send unread-notification digests to users

(`run_contradiction_alert_task` and the `interest_match` check were removed
alongside the Conflicts and Memory features.)
"""
from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.metrics import TASK_FAILURES
from app.workers.celery_app import celery_app

configure_logging()
log = get_logger(__name__)


# ─── async DB context manager for workers ────────────────────────────────────

@asynccontextmanager
async def _async_db():
    """Open a fresh async database session scoped to a single worker invocation."""
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            yield session
    finally:
        await engine.dispose()


# ─── run_all_alert_checks ─────────────────────────────────────────────────────

@celery_app.task(
    name="run_all_alert_checks",
    bind=True,
    queue="alerts",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=2,
)
def run_all_alert_checks_task(self, document_id: str) -> str:
    """Evaluate topic_keyword and entity_mention rules for a document."""

    async def _run(doc_id_str: str) -> None:
        from app.services.alerts import check_entity_mention, check_keyword_match

        doc_id = uuid.UUID(doc_id_str)
        async with _async_db() as session:
            await check_keyword_match(doc_id, session)

        async with _async_db() as session:
            await check_entity_mention(doc_id, session)

    try:
        asyncio.run(_run(document_id))
        log.info("run_all_alert_checks.done", document_id=document_id)
        return document_id
    except Exception as e:
        TASK_FAILURES.labels(task="run_all_alert_checks").inc()
        log.exception("run_all_alert_checks.failed", document_id=document_id)
        try:
            import sentry_sdk
            sentry_sdk.capture_exception(e)
        except Exception:
            pass
        raise


# ─── send_email_digest ────────────────────────────────────────────────────────

@celery_app.task(
    name="send_email_digest",
    bind=True,
    queue="alerts",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=2,
)
def send_email_digest_task(self) -> str:
    """Send a digest email to each user who has unread notifications from the last 24h."""
    from app.db.sync_session import get_sync_session
    from app.models.alert import Notification

    session = get_sync_session()
    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    try:
        # Find users with unread notifications in the last 24h
        rows = session.execute(
            select(Notification.user_id)
            .where(
                Notification.read_at.is_(None),
                Notification.created_at >= cutoff,
            )
            .distinct()
        ).scalars().all()

        digest_count = 0
        for user_id in rows:
            try:
                from app.models.workflow import EmailSettings
                from app.services.workflows import send_email_action

                # Load email settings for the user
                es = session.execute(
                    select(EmailSettings).where(
                        EmailSettings.user_id == user_id,
                        EmailSettings.enabled.is_(True),
                    )
                ).scalar_one_or_none()
                if es is None:
                    continue

                # Load all unread notifications for the digest
                notifs = session.execute(
                    select(Notification).where(
                        Notification.user_id == user_id,
                        Notification.read_at.is_(None),
                        Notification.created_at >= cutoff,
                    ).order_by(Notification.created_at.desc())
                ).scalars().all()

                if not notifs:
                    continue

                # Build digest body
                lines = [f"You have {len(notifs)} unread notification(s):\n"]
                for n in notifs:
                    lines.append(f"- {n.title}: {n.body}")
                    if n.link:
                        lines.append(f"  Link: {n.link}")
                email_body = "\n".join(lines)

                success = send_email_action(
                    es,
                    subject="NexusMind Notification Digest",
                    body=email_body,
                    jwt_secret=settings.jwt_secret,
                )
                if success:
                    digest_count += 1

            except Exception:
                log.exception("send_email_digest.user_failed", user_id=str(user_id))

        log.info("send_email_digest.done", digests_sent=digest_count)
        return f"digests_sent={digest_count}"

    except Exception as e:
        session.rollback()
        TASK_FAILURES.labels(task="send_email_digest").inc()
        log.exception("send_email_digest.failed")
        try:
            import sentry_sdk
            sentry_sdk.capture_exception(e)
        except Exception:
            pass
        raise
    finally:
        session.close()
