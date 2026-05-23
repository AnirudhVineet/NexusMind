"""Beat-scheduled maintenance tasks for the knowledge graph.

These tasks acquire a Redis single-flight lock so that overlapping schedules
(or a stuck previous run) don't double-execute.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import redis
from sqlalchemy import delete, func, select

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.metrics import GRAPH_EDGES_TOTAL, GRAPH_ENTITIES_TOTAL, TASK_FAILURES
from app.db.sync_session import get_sync_session
from app.models.entity import Entity
from app.models.entity_edge import EntityEdge
from app.workers.celery_app import celery_app

configure_logging()
log = get_logger(__name__)


@contextmanager
def _redis_lock(key: str, ttl_seconds: int):
    settings = get_settings()
    client = redis.from_url(settings.redis_url)
    acquired = client.set(key, "1", nx=True, ex=ttl_seconds)
    try:
        yield bool(acquired)
    finally:
        if acquired:
            try:
                client.delete(key)
            except Exception:
                pass


def _refresh_graph_gauges(session) -> None:
    total_entities = session.execute(select(func.count()).select_from(Entity)).scalar_one()
    GRAPH_ENTITIES_TOTAL.set(int(total_entities or 0))

    rows = session.execute(
        select(EntityEdge.relation_type, func.count())
        .group_by(EntityEdge.relation_type)
    ).all()
    for rtype, count in rows:
        GRAPH_EDGES_TOTAL.labels(relation_type=rtype).set(int(count))


@celery_app.task(name="prune_low_conf_edges", queue="maintenance")
def prune_low_conf_edges() -> dict:
    """Delete edges below the confidence threshold whose evidence is stale.

    "Stale" = no new evidence chunk in the last 7 days.
    """
    settings = get_settings()
    with _redis_lock("lock:prune_low_conf_edges", ttl_seconds=60 * 30) as got:
        if not got:
            log.info("prune_low_conf_edges.skipped_lock_held")
            return {"skipped": True}

        session = get_sync_session()
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            result = session.execute(
                delete(EntityEdge).where(
                    EntityEdge.confidence < settings.relation_min_confidence,
                    EntityEdge.created_at < cutoff,
                )
            )
            session.commit()
            deleted = int(result.rowcount or 0)
            _refresh_graph_gauges(session)
            session.commit()
            log.info("prune_low_conf_edges.done", deleted=deleted)
            return {"deleted": deleted}
        except Exception as e:
            session.rollback()
            TASK_FAILURES.labels(task="prune_low_conf_edges").inc()
            log.exception("prune_low_conf_edges.failed")
            try:
                import sentry_sdk

                sentry_sdk.capture_exception(e)
            except Exception:
                pass
            raise
        finally:
            session.close()


@celery_app.task(name="recompute_topics", queue="maintenance")
def recompute_topics() -> dict:
    """Daily BERTopic + LLM zero-shot topic tagging across the user corpus.

    Implemented in app.services.topics; this Celery wrapper handles the
    Redis lock and metrics. If the topic service is not yet available
    (Phase 2 incremental rollout), the task no-ops.
    """
    with _redis_lock("lock:recompute_topics", ttl_seconds=60 * 60 * 2) as got:
        if not got:
            log.info("recompute_topics.skipped_lock_held")
            return {"skipped": True}

        try:
            from app.services.topics import recompute_all_topics
        except ImportError:
            log.info("recompute_topics.service_not_available")
            return {"skipped": True, "reason": "service_unavailable"}

        try:
            stats = recompute_all_topics()
            log.info("recompute_topics.done", **stats)
            return stats
        except Exception as e:
            TASK_FAILURES.labels(task="recompute_topics").inc()
            log.exception("recompute_topics.failed")
            try:
                import sentry_sdk

                sentry_sdk.capture_exception(e)
            except Exception:
                pass
            raise
