"""Shared helpers for Celery workers that bridge sync Celery → async code."""
from __future__ import annotations

import asyncio
from typing import Awaitable


def run_async_task(coro: Awaitable[None]) -> None:
    """Run `coro` in a fresh event loop and dispose the async DB engine
    afterward.

    `asyncio.run` creates a new event loop, runs the coroutine, then closes
    the loop. But our module-level `AsyncSessionLocal` engine pools asyncpg
    connections whose transports are bound to whatever loop they were
    created on. Once that loop closes, those pooled connections are zombies.
    On the *next* Celery task `asyncio.run` builds a new loop; SQLAlchemy's
    `pool_pre_ping` then tries to validate a connection against the new
    loop, hits the dead transport, and raises:

        RuntimeError: Event loop is closed

    That exception bubbles before the task can mark its DB row as "running"
    — so the row stays at status="queued" forever. To the UI it looks like
    the second job never started.

    Disposing the engine in a `finally` releases every pooled connection
    before the loop closes, so the next task starts clean.
    """
    from app.db.session import engine

    async def _wrapper() -> None:
        try:
            await coro
        finally:
            await engine.dispose()

    asyncio.run(_wrapper())
