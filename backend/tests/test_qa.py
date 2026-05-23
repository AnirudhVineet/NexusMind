"""
Q&A endpoint tests focused on the no-source guard and citation parsing.
The LLM client is mocked so these run without network or API keys.

Database-dependent assertions are skipped when Postgres isn't reachable.
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
            token = r.json()["access_token"]
            ac.headers.update({"Authorization": f"Bearer {token}"})
            yield ac


@pytest.mark.asyncio
async def test_no_source_fallback_skips_llm(authed_client):
    """With no documents uploaded, /qa must NOT call the LLM."""
    with patch("app.api.qa.call_llm") as mock_llm, \
         patch("app.api.qa.get_embedding_service") as mock_embed:
        mock_embed.return_value.embed_query = AsyncMock(return_value=[0.0] * 768)

        r = await authed_client.post("/qa", json={"question": "anything?"})
        assert r.status_code == 200
        body = r.json()
        assert body["no_source_found"] is True
        assert body["citations"] == []
        assert body["confidence_score"] == 0.0
        mock_llm.assert_not_called()
