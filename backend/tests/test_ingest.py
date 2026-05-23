"""
Smoke tests for /ingest input validation. The Celery enqueue and MinIO upload are
mocked, so these run without external services.
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
async def test_unsupported_mime_returns_415(authed_client):
    with patch("app.api.documents.StorageService"), \
         patch("app.api.documents._enqueue_pipeline"):
        r = await authed_client.post(
            "/ingest",
            files={"file": ("a.zip", b"PK\x03\x04junk", "application/zip")},
        )
    assert r.status_code == 415


@pytest.mark.asyncio
async def test_oversized_file_returns_413(authed_client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "max_upload_bytes", 16)
    with patch("app.api.documents.StorageService"), \
         patch("app.api.documents._enqueue_pipeline"):
        r = await authed_client.post(
            "/ingest",
            files={"file": ("a.txt", b"x" * 1024, "text/plain")},
        )
    assert r.status_code == 413


@pytest.mark.asyncio
async def test_duplicate_upload_returns_existing(authed_client):
    fake_storage = AsyncMock()
    fake_storage.upload = AsyncMock(return_value="key")
    with patch("app.api.documents.StorageService", return_value=fake_storage), \
         patch("app.api.documents._enqueue_pipeline") as mock_enqueue:
        body = b"hello world\n"
        r1 = await authed_client.post(
            "/ingest", files={"file": ("a.txt", body, "text/plain")}
        )
        assert r1.status_code == 201
        first_id = r1.json()["document_id"]

        r2 = await authed_client.post(
            "/ingest", files={"file": ("a.txt", body, "text/plain")}
        )
        assert r2.status_code == 200
        assert r2.json()["document_id"] == first_id
        # only the first call should enqueue
        assert mock_enqueue.call_count == 1
