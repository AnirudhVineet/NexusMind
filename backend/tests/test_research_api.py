"""Tests for research API endpoint validation — Phase 4 Track B.

Integration tests — skipped when Postgres is not reachable.
"""
import asyncio
import uuid
from unittest.mock import AsyncMock, patch

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


pytestmark = pytest.mark.skipif(
    not _db_reachable(),
    reason="Postgres not reachable; integration tests skipped",
)


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
async def test_create_brief_returns_202(authed_client):
    with patch("app.api.research.celery_app") as mock_celery:
        mock_celery.send_task = AsyncMock()
        r = await authed_client.post("/api/research/briefs", json={"topic": "AI Ethics"})

    assert r.status_code in (200, 201, 202)
    data = r.json()
    assert "id" in data


@pytest.mark.asyncio
async def test_list_briefs(authed_client):
    r = await authed_client.get("/api/research/briefs")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list) or "items" in data


@pytest.mark.asyncio
async def test_get_nonexistent_brief(authed_client):
    fake_id = str(uuid.uuid4())
    r = await authed_client.get(f"/api/research/briefs/{fake_id}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_create_brief_empty_topic_rejected(authed_client):
    r = await authed_client.post("/api/research/briefs", json={"topic": ""})
    assert r.status_code in (400, 422)
