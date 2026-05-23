"""Tests for content API — Phase 4 Track H.

Integration tests — skipped when Postgres is not reachable.
"""
import asyncio
import uuid

import httpx
import pytest
from asgi_lifespan import LifespanManager
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings


def _db_reachable() -> bool:
    async def _ping():
        engine = create_async_engine(get_settings().database_url)
        try:
            async with engine.connect() as c:
                await c.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
        finally:
            await engine.dispose()
    try:
        return asyncio.run(_ping())
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_reachable(), reason="Postgres not reachable")


@pytest.fixture
async def authed_client():
    from app.main import app
    async with LifespanManager(app):
        async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
            email = f"u-{uuid.uuid4().hex[:8]}@example.com"
            await ac.post("/auth/register", json={"email": email, "password": "password123"})
            r = await ac.post("/auth/token", json={"email": email, "password": "password123"})
            ac.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})
            yield ac


@pytest.mark.asyncio
async def test_list_content(authed_client):
    r = await authed_client.get("/api/content")
    assert r.status_code == 200

@pytest.mark.asyncio
async def test_get_nonexistent(authed_client):
    r = await authed_client.get(f"/api/content/{uuid.uuid4()}")
    assert r.status_code == 404
