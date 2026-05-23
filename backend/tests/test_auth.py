"""
Integration tests for /auth/* endpoints.

These require a running Postgres reachable via DATABASE_URL with the schema applied
(`alembic upgrade head` against the test DB). Run via:

    docker compose up -d postgres redis minio
    DATABASE_URL=... DATABASE_SYNC_URL=... pytest backend/tests/test_auth.py

Skipped when the database is unreachable, so the rest of the suite stays green.
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


pytestmark = pytest.mark.skipif(
    not _db_reachable(),
    reason="Postgres not reachable; integration tests skipped",
)


@pytest.fixture
async def client():
    from app.main import app

    async with LifespanManager(app):
        async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
            yield ac


async def _register(client, email: str, password: str = "password123"):
    return await client.post("/auth/register", json={"email": email, "password": password})


@pytest.mark.asyncio
async def test_register_and_login(client):
    email = f"u-{uuid.uuid4().hex[:8]}@example.com"
    r = await _register(client, email)
    assert r.status_code == 201

    r = await client.post("/auth/token", json={"email": email, "password": "password123"})
    assert r.status_code == 200
    token = r.json()["access_token"]

    r = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == email


@pytest.mark.asyncio
async def test_register_duplicate_returns_409(client):
    email = f"u-{uuid.uuid4().hex[:8]}@example.com"
    r1 = await _register(client, email)
    assert r1.status_code == 201
    r2 = await _register(client, email)
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_bad_password_returns_401(client):
    email = f"u-{uuid.uuid4().hex[:8]}@example.com"
    await _register(client, email)
    r = await client.post("/auth/token", json={"email": email, "password": "wrong-password"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_requires_token(client):
    r = await client.get("/documents")
    assert r.status_code == 401
