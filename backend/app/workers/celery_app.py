from celery import Celery
from celery.signals import worker_process_init

from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()

celery_app = Celery(
    "nexusmind",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.workers.parse",
        "app.workers.chunk",
        "app.workers.embed",
        "app.workers.ner",
        "app.workers.relations",
        "app.workers.intelligence",
        "app.workers.maintenance",
        "app.workers.credibility",
        # Phase 3 workers
        "app.workers.annotations",
        "app.workers.cards",
        # Phase 4 workers
        "app.workers.research",
        "app.workers.content",
        # Phase 5 workers
        "app.workers.media",
        "app.workers.media_cleanup",
    ],
)

celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_default_retry_delay=10,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    task_time_limit=60 * 30,
    task_soft_time_limit=60 * 25,
    broker_transport_options={
        "visibility_timeout": 60 * 60,
    },
    task_default_queue="default",
    task_queues={
        "default": {"exchange": "default", "routing_key": "default"},
        "dead_letter": {"exchange": "dead_letter", "routing_key": "dead_letter"},
        "ner": {"exchange": "ner", "routing_key": "ner"},
        "relations": {"exchange": "relations", "routing_key": "relations"},
        "intelligence": {"exchange": "intelligence", "routing_key": "intelligence"},
        "maintenance": {"exchange": "maintenance", "routing_key": "maintenance"},
        "credibility": {"exchange": "credibility", "routing_key": "credibility"},
        # Phase 3 queues
        "ocr": {"exchange": "ocr", "routing_key": "ocr"},
        "transcription": {"exchange": "transcription", "routing_key": "transcription"},
        "cards": {"exchange": "cards", "routing_key": "cards"},
        # Phase 4 queues
        "research": {"exchange": "research", "routing_key": "research"},
        # Phase 5 queue
        "reel": {"exchange": "reel", "routing_key": "reel"},
        # Content repurposing — dedicated queue so script/caption/thread/meme
        # generation isn't blocked behind heavy NER/relations/claims tasks on
        # the shared `intelligence` queue (which runs --pool=solo).
        "content": {"exchange": "content", "routing_key": "content"},
    },
    beat_schedule={
        "prune-low-confidence-edges-weekly": {
            "task": "prune_low_conf_edges",
            "schedule": 60 * 60 * 24 * 7,  # 7 days
            "options": {"queue": "maintenance"},
        },
        "recompute-topics-daily": {
            "task": "recompute_topics",
            "schedule": 60 * 60 * 24,
            "options": {"queue": "maintenance"},
        },
        # Phase 5 beat tasks
        "cleanup-expired-media-hourly": {
            "task": "cleanup_expired_media",
            "schedule": 60 * 60,
            "options": {"queue": "maintenance"},
        },
        "cleanup-orphan-scratch-dirs-hourly": {
            "task": "cleanup_orphan_scratch_dirs",
            "schedule": 60 * 60,
            "options": {"queue": "maintenance"},
        },
    },
)


@worker_process_init.connect
def _init_worker(*args, **kwargs):
    configure_logging()


def init_sentry() -> None:
    if not settings.sentry_dsn_backend:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration

        sentry_sdk.init(
            dsn=settings.sentry_dsn_backend,
            environment=settings.environment,
            integrations=[CeleryIntegration()],
            traces_sample_rate=0.1,
        )
    except Exception:
        pass


init_sentry()
