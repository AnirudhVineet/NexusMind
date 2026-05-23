"""Graph export Celery workers — Phase 4 Track E.

graph_export_task         — execute a queued export job
cleanup_expired_graph_exports_task — purge expired export files and DB rows
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.metrics import TASK_FAILURES
from app.db.sync_session import get_sync_session
from app.models.graph_export import GraphExport
from app.services.graph_export import load_subgraph, serialize_graph
from app.workers.celery_app import celery_app

configure_logging()
log = get_logger(__name__)


@celery_app.task(
    name="graph_export_task",
    bind=True,
    queue="default",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=3,
)
def graph_export_task(self, job_id: str) -> str:
    """Build and serialise the knowledge-graph for a pending export job."""
    session = get_sync_session()
    try:
        job_uuid = uuid.UUID(job_id)
        job: GraphExport | None = session.execute(
            select(GraphExport).where(GraphExport.id == job_uuid)
        ).scalar_one_or_none()

        if job is None:
            log.warning("graph_export_task.job_not_found", job_id=job_id)
            return job_id

        # ── mark running ───────────────────────────────────────────────────────
        job.status = "running"
        session.commit()

        # ── determine output path ──────────────────────────────────────────────
        settings = get_settings()
        data_dir = Path(settings.storage_dir)
        export_dir = data_dir / "exports" / "graph"
        export_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(export_dir / f"{job_id}.{job.format}")

        # ── build + serialise ──────────────────────────────────────────────────
        graph = load_subgraph(job.user_id, session, job.filters or {})
        file_size = serialize_graph(graph, job.format, output_path)

        # ── update row ─────────────────────────────────────────────────────────
        job.status = "complete"
        job.file_path = output_path
        job.file_size_bytes = file_size
        job.completed_at = datetime.now(timezone.utc)
        session.commit()

        log.info(
            "graph_export_task.done",
            job_id=job_id,
            format=job.format,
            nodes=graph.number_of_nodes(),
            edges=graph.number_of_edges(),
            file_size=file_size,
        )
        return job_id

    except Exception as exc:
        session.rollback()
        TASK_FAILURES.labels(task="graph_export_task").inc()
        log.exception("graph_export_task.failed", job_id=job_id)

        # Best-effort: mark the row as failed.
        try:
            job_uuid = uuid.UUID(job_id)
            job = session.execute(
                select(GraphExport).where(GraphExport.id == job_uuid)
            ).scalar_one_or_none()
            if job is not None:
                job.status = "failed"
                session.commit()
        except Exception:
            session.rollback()

        try:
            import sentry_sdk

            sentry_sdk.capture_exception(exc)
        except Exception:
            pass

        raise

    finally:
        session.close()


@celery_app.task(
    name="cleanup_expired_graph_exports",
    bind=True,
    queue="maintenance",
)
def cleanup_expired_graph_exports_task(self) -> str:
    """Delete expired export files from disk and remove their DB rows."""
    session = get_sync_session()
    try:
        now = datetime.now(timezone.utc)
        expired_jobs = session.execute(
            select(GraphExport).where(GraphExport.expires_at < now)
        ).scalars().all()

        deleted = 0
        for job in expired_jobs:
            if job.file_path:
                try:
                    Path(job.file_path).unlink(missing_ok=True)
                except Exception:
                    log.warning(
                        "cleanup_expired_graph_exports.unlink_failed",
                        path=job.file_path,
                    )
            session.delete(job)
            deleted += 1

        session.commit()
        log.info("cleanup_expired_graph_exports.done", deleted=deleted)
        return str(deleted)

    except Exception as exc:
        session.rollback()
        TASK_FAILURES.labels(task="cleanup_expired_graph_exports").inc()
        log.exception("cleanup_expired_graph_exports.failed")
        try:
            import sentry_sdk

            sentry_sdk.capture_exception(exc)
        except Exception:
            pass
        raise

    finally:
        session.close()
