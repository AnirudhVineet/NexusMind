"""Automation Workflow Celery workers — Phase 4 Track F.

execute_workflow_action_task  — dispatch a single workflow action
poll_rss_feeds_task           — beat task: find feeds due for fetching
fetch_rss_feed_task           — fetch one RSS/Atom feed and ingest new items
card_due_threshold_check_task — beat task: fire card_due_threshold events
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.metrics import TASK_FAILURES
from app.db.sync_session import get_sync_session
from app.workers.celery_app import celery_app

configure_logging()
log = get_logger(__name__)


# ─── execute_workflow_action ──────────────────────────────────────────────────


@celery_app.task(
    name="execute_workflow_action",
    bind=True,
    queue="default",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=3,
)
def execute_workflow_action_task(
    self, workflow_id: str, run_id: str, event_payload: str
) -> str:
    """Dispatch the action for a single matched workflow run."""
    session = get_sync_session()
    try:
        from app.models.workflow import EmailSettings, Workflow, WorkflowRun
        from app.services.workflows import fire_webhook_action, send_email_action

        settings = get_settings()

        wf_uuid = uuid.UUID(workflow_id)
        run_uuid = uuid.UUID(run_id)
        payload: dict = json.loads(event_payload)

        wf: Workflow | None = session.execute(
            select(Workflow).where(Workflow.id == wf_uuid)
        ).scalar_one_or_none()

        run: WorkflowRun | None = session.execute(
            select(WorkflowRun).where(WorkflowRun.id == run_uuid)
        ).scalar_one_or_none()

        if wf is None or run is None:
            log.warning(
                "execute_workflow_action.not_found",
                workflow_id=workflow_id,
                run_id=run_id,
            )
            return run_id

        success = True
        error_msg: str | None = None

        try:
            action = wf.action_type
            config = wf.action_config or {}

            if action == "send_email":
                es: EmailSettings | None = session.execute(
                    select(EmailSettings).where(EmailSettings.user_id == wf.user_id)
                ).scalar_one_or_none()
                if es is None or not es.enabled:
                    raise RuntimeError("Email settings not configured or disabled")

                subject = config.get("subject", "NexusMind Workflow Alert")
                body = config.get("body_template", json.dumps(payload, indent=2))
                success = send_email_action(es, subject, body, settings.jwt_secret)
                if not success:
                    raise RuntimeError("send_email_action returned False")

            elif action == "fire_webhook":
                webhook_url = config.get("url", "")
                webhook_secret = config.get("webhook_secret", "")
                if not webhook_url:
                    raise RuntimeError("fire_webhook: no url in action_config")
                success = fire_webhook_action(webhook_url, payload, webhook_secret)
                if not success:
                    raise RuntimeError("fire_webhook_action returned False")

            elif action == "mark_tag":
                from app.models.document import Document

                doc_id_str = payload.get("document_id")
                tag = config.get("tag", "workflow-tagged")
                if doc_id_str:
                    doc_uuid = uuid.UUID(doc_id_str)
                    doc: Document | None = session.execute(
                        select(Document).where(Document.id == doc_uuid)
                    ).scalar_one_or_none()
                    if doc is not None:
                        intel = doc.intelligence or {}
                        tags_list: list = intel.get("tags", [])
                        if tag not in tags_list:
                            tags_list.append(tag)
                        intel["tags"] = tags_list
                        doc.intelligence = intel
                        session.commit()

            elif action == "create_research_brief":
                topic = config.get("topic") or payload.get("topic", "")
                if topic:
                    celery_app.send_task(
                        "generate_research_brief",
                        args=[str(wf.user_id), topic],
                        queue="default",
                    )

            elif action == "generate_cards":
                doc_id_str = payload.get("document_id")
                if doc_id_str:
                    from app.workers.cards import generate_cards_task

                    generate_cards_task.apply_async(args=[doc_id_str])

            elif action == "push_notification":
                # Track G will deliver; we just insert a record for it
                message = config.get("message", "NexusMind workflow triggered")
                log.info(
                    "execute_workflow_action.push_notification_pending",
                    user_id=str(wf.user_id),
                    message=message,
                    payload=payload,
                )
                # Actual notification delivery deferred to Track G

            else:
                log.warning(
                    "execute_workflow_action.unknown_action_type",
                    action_type=action,
                    workflow_id=workflow_id,
                )

        except Exception as action_exc:
            success = False
            error_msg = str(action_exc)
            log.exception(
                "execute_workflow_action.action_failed",
                workflow_id=workflow_id,
                action_type=wf.action_type,
            )

        # Update run status
        run.status = "complete" if success else "failed"
        run.completed_at = datetime.now(timezone.utc)
        if error_msg:
            run.error_message = error_msg

        session.commit()
        log.info(
            "execute_workflow_action.done",
            workflow_id=workflow_id,
            run_id=run_id,
            status=run.status,
        )
        return run_id

    except Exception as exc:
        session.rollback()
        TASK_FAILURES.labels(task="execute_workflow_action").inc()
        log.exception(
            "execute_workflow_action.failed",
            workflow_id=workflow_id,
            run_id=run_id,
        )
        try:
            import sentry_sdk

            sentry_sdk.capture_exception(exc)
        except Exception:
            pass
        raise

    finally:
        session.close()


# ─── poll_rss_feeds ────────────────────────────────────────────────────────────


@celery_app.task(
    name="poll_rss_feeds",
    bind=True,
    queue="default",
)
def poll_rss_feeds_task(self) -> str:
    """Beat task: find all enabled feeds that are due for fetching and enqueue them."""
    session = get_sync_session()
    try:
        from app.models.rss_feed import RssFeed

        # Load all enabled feeds, then filter in Python based on interval.
        # This avoids complex cross-dialect SQL for interval arithmetic.
        all_enabled = session.execute(
            select(RssFeed).where(RssFeed.enabled.is_(True))
        ).scalars().all()

        now = datetime.now(timezone.utc)
        due_feeds = []
        for f in all_enabled:
            if f.last_fetched_at is None:
                due_feeds.append(f)
            else:
                from datetime import timedelta

                next_fetch = f.last_fetched_at.replace(tzinfo=timezone.utc) + timedelta(
                    minutes=f.interval_minutes
                )
                if now >= next_fetch:
                    due_feeds.append(f)

        count = 0
        for feed in due_feeds:
            fetch_rss_feed_task.apply_async(args=[str(feed.id)])
            count += 1

        log.info("poll_rss_feeds.done", queued=count)
        return str(count)

    except Exception as exc:
        session.rollback()
        TASK_FAILURES.labels(task="poll_rss_feeds").inc()
        log.exception("poll_rss_feeds.failed")
        try:
            import sentry_sdk

            sentry_sdk.capture_exception(exc)
        except Exception:
            pass
        raise

    finally:
        session.close()


# ─── fetch_rss_feed ────────────────────────────────────────────────────────────


@celery_app.task(
    name="fetch_rss_feed",
    bind=True,
    queue="default",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=3,
)
def fetch_rss_feed_task(self, feed_id: str) -> str:
    """Fetch one RSS/Atom feed, ingest new items, and update cache headers."""
    session = get_sync_session()
    try:
        import feedparser

        from app.models.document import Document
        from app.models.rss_feed import RssFeed, RssSeenItem

        feed_uuid = uuid.UUID(feed_id)
        feed: RssFeed | None = session.execute(
            select(RssFeed).where(RssFeed.id == feed_uuid)
        ).scalar_one_or_none()

        if feed is None:
            log.warning("fetch_rss_feed.not_found", feed_id=feed_id)
            return feed_id

        # Build conditional-GET headers
        kwargs: dict = {}
        if feed.last_etag:
            kwargs["etag"] = feed.last_etag
        if feed.last_modified:
            kwargs["modified"] = feed.last_modified

        parsed = feedparser.parse(feed.url, **kwargs)

        # 304 Not Modified
        if getattr(parsed, "status", None) == 304:
            feed.last_fetched_at = datetime.now(timezone.utc)
            session.commit()
            log.info("fetch_rss_feed.not_modified", feed_id=feed_id)
            return feed_id

        new_docs = 0
        for entry in parsed.entries:
            item_guid: str = getattr(entry, "id", None) or getattr(entry, "link", None) or ""
            if not item_guid:
                continue

            # Check if already seen
            seen = session.execute(
                select(RssSeenItem).where(
                    RssSeenItem.feed_id == feed_uuid,
                    RssSeenItem.item_guid == item_guid,
                )
            ).scalar_one_or_none()
            if seen is not None:
                continue

            # Insert seen record
            seen_row = RssSeenItem(feed_id=feed_uuid, item_guid=item_guid)
            session.add(seen_row)

            # Create Document row
            entry_title: str = getattr(entry, "title", "") or item_guid
            entry_link: str = getattr(entry, "link", "") or item_guid

            # Build a stable content_hash from the guid so we don't duplicate
            content_hash = hashlib.sha256(item_guid.encode()).hexdigest()

            existing_doc = session.execute(
                select(Document).where(
                    Document.user_id == feed.user_id,
                    Document.content_hash == content_hash,
                )
            ).scalar_one_or_none()

            if existing_doc is not None:
                continue

            doc = Document(
                user_id=feed.user_id,
                filename=entry_title[:255],
                source_type="web",
                mime_type="text/plain",
                file_size_bytes=None,
                content_hash=content_hash,
                storage_path=f"{feed.user_id}/rss/{feed_id}/{item_guid[:64]}",
                source_url=entry_link,
                ingestion_metadata={
                    "feed_id": str(feed_uuid),
                    "feed_title": feed.title,
                    "item_guid": item_guid,
                },
                processing_status="queued",
            )
            session.add(doc)
            session.flush()  # get doc.id

            # Enqueue parse pipeline
            celery_app.send_task("parse_document", args=[str(doc.id)])
            new_docs += 1

        # Update feed metadata
        feed.last_fetched_at = datetime.now(timezone.utc)
        feed.last_etag = getattr(parsed, "etag", None) or feed.last_etag
        feed.last_modified = getattr(parsed, "modified", None) or feed.last_modified

        session.commit()
        log.info(
            "fetch_rss_feed.done",
            feed_id=feed_id,
            new_docs=new_docs,
        )
        return feed_id

    except Exception as exc:
        session.rollback()
        TASK_FAILURES.labels(task="fetch_rss_feed").inc()
        log.exception("fetch_rss_feed.failed", feed_id=feed_id)
        try:
            import sentry_sdk

            sentry_sdk.capture_exception(exc)
        except Exception:
            pass
        raise

    finally:
        session.close()


# ─── card_due_threshold_check ──────────────────────────────────────────────────


@celery_app.task(
    name="card_due_threshold_check",
    bind=True,
    queue="default",
)
def card_due_threshold_check_task(self) -> str:
    """Beat task: fire card_due_threshold workflow events for users with many due cards."""
    session = get_sync_session()
    try:

        from app.models.flashcard import Flashcard
        from app.services.workflows import evaluate_workflows

        DUE_THRESHOLD = 5

        today = datetime.now(timezone.utc).date()

        # Group by user_id and count due cards
        rows = session.execute(
            select(Flashcard.user_id, func.count(Flashcard.id).label("due_count"))
            .where(
                Flashcard.due_date <= today,
                Flashcard.suspended.is_(False),
            )
            .group_by(Flashcard.user_id)
        ).all()

        users_checked = 0
        for user_id, due_count in rows:
            if due_count >= DUE_THRESHOLD:
                evaluate_workflows(
                    session,
                    "card_due_threshold",
                    {"due_count": due_count},
                    user_id,
                )
            users_checked += 1

        log.info(
            "card_due_threshold_check.done",
            users_checked=users_checked,
            threshold=DUE_THRESHOLD,
        )
        return str(users_checked)

    except Exception as exc:
        session.rollback()
        TASK_FAILURES.labels(task="card_due_threshold_check").inc()
        log.exception("card_due_threshold_check.failed")
        try:
            import sentry_sdk

            sentry_sdk.capture_exception(exc)
        except Exception:
            pass
        raise

    finally:
        session.close()
