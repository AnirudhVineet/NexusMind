"""Event logger middleware — Phase 4 Personal Memory Layer.

After each successful POST response (status < 400), fires a background task
that logs the matching event into user_events. JWT is decoded without full
verification just to extract the user_id (sub claim). Failures are silently
swallowed so the middleware never disrupts the main request path.
"""
from __future__ import annotations

import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

PATH_TO_EVENT: dict[str, str] = {
    "/qa": "query",
    "/qa/stream": "query",
    "/api/search": "search_performed",
    "/api/cards/": "card_reviewed",   # POST /api/cards/{id}/review
    "/api/annotations": "annotation_created",
}


def _extract_user_id(authorization: str | None) -> uuid.UUID | None:
    """Decode JWT header without verifying signature to extract sub/user_id."""
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1]
    try:
        import jwt as pyjwt

        payload = pyjwt.decode(token, options={"verify_signature": False})
        sub = payload.get("sub")
        if sub:
            return uuid.UUID(sub)
    except Exception:
        pass
    return None


def _match_event_type(path: str) -> str | None:
    """Return the event type for the given request path, or None if no match."""
    for prefix, event_type in PATH_TO_EVENT.items():
        if path == prefix or path.startswith(prefix):
            return event_type
    return None


async def _log_event(user_id: uuid.UUID, event_type: str, path: str) -> None:
    """Insert a UserEvent row. Uses a fresh async session."""
    try:
        from app.db.session import AsyncSessionLocal
        from app.models.user_event import UserEvent

        async with AsyncSessionLocal() as session:
            event = UserEvent(
                user_id=user_id,
                event_type=event_type,
                event_metadata={"path": path},
            )
            session.add(event)
            await session.commit()
    except Exception:
        pass


class EventLoggerMiddleware(BaseHTTPMiddleware):
    """Middleware that auto-logs user events for specific POST endpoints."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Only log successful POST requests
        if request.method != "POST" or response.status_code >= 400:
            return response

        path = request.url.path
        event_type = _match_event_type(path)
        if event_type is None:
            return response

        user_id = _extract_user_id(request.headers.get("authorization"))
        if user_id is None:
            return response

        # Fire-and-forget via background task attached to the response
        try:
            import asyncio

            asyncio.ensure_future(_log_event(user_id, event_type, path))
        except Exception:
            pass

        return response
