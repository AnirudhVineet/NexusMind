import time
import uuid

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import annotations, auth, cards, conversations, credibility, documents, graph, health, ingest, intelligence, metrics, qa
from app.api import events, research, graph_export, workflows, feeds, email_settings, alerts, notifications, push, content
# Phase 5 routers
from app.api import media as media_api
from app.api import media_narration as media_narration_api
from app.api import meme_templates as meme_templates_api
from app.api import media_storyboards as media_storyboards_api
from app.api import publish as publish_api
from app.api import public_share as public_share_api
from app.api import brandkit as brandkit_api
from app.api import media_quota as media_quota_api
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging, get_logger
from app.middleware.event_logger import EventLoggerMiddleware


def _init_sentry() -> None:
    settings = get_settings()
    if not settings.sentry_dsn_backend:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration

        sentry_sdk.init(
            dsn=settings.sentry_dsn_backend,
            environment=settings.environment,
            integrations=[FastApiIntegration()],
            traces_sample_rate=0.1,
        )
    except Exception:
        pass


def create_app() -> FastAPI:
    configure_logging()
    _init_sentry()
    log = get_logger("app")

    app = FastAPI(title="NexusMind API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(EventLoggerMiddleware)

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            path=request.url.path,
            method=request.method,
        )
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            duration_ms = int((time.perf_counter() - started) * 1000)
            log.info(
                "request",
                status_code=status_code,
                duration_ms=duration_ms,
            )
            structlog.contextvars.clear_contextvars()

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        request_id = request.headers.get("X-Request-ID")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.message,
                "code": exc.code,
                "request_id": request_id,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        log.exception("unhandled_exception")
        request_id = request.headers.get("X-Request-ID")
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "code": "internal_error",
                "request_id": request_id,
            },
        )

    app.include_router(health.router)
    app.include_router(metrics.router)
    app.include_router(auth.router)
    app.include_router(documents.router)
    app.include_router(qa.router)
    app.include_router(graph.router)
    app.include_router(intelligence.router)
    app.include_router(credibility.router)
    app.include_router(conversations.router)
    app.include_router(ingest.router)
    app.include_router(annotations.router)
    app.include_router(cards.router)
    # Phase 4 routers
    app.include_router(events.router)
    app.include_router(research.router)
    app.include_router(graph_export.router)
    app.include_router(workflows.router)
    app.include_router(feeds.router)
    app.include_router(email_settings.router)
    app.include_router(alerts.router)
    app.include_router(notifications.router)
    app.include_router(push.router)
    app.include_router(content.router)
    # Phase 5
    app.include_router(media_api.router)
    app.include_router(media_narration_api.router)
    app.include_router(meme_templates_api.router)
    app.include_router(media_storyboards_api.router)
    app.include_router(publish_api.router)
    app.include_router(public_share_api.router)
    app.include_router(brandkit_api.router)
    app.include_router(media_quota_api.router)

    return app


app = create_app()
