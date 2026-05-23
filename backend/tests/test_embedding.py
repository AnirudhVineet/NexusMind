import json

import pytest

from app.services.embedding import EmbeddingService


@pytest.mark.asyncio
async def test_embed_query_calls_api_and_caches(monkeypatch):
    svc = EmbeddingService()

    fake_vec = [0.1] * 768

    captured: dict = {}

    async def fake_get(key):
        captured["get_key"] = key
        return None

    async def fake_set(key, val, ex=None):
        captured["set_key"] = key
        captured["set_val"] = val
        captured["set_ex"] = ex

    monkeypatch.setattr(svc.cache, "get", fake_get)
    monkeypatch.setattr(svc.cache, "set", fake_set)

    async def fake_embed_one(text, task_type):
        assert task_type == "retrieval_query"
        return fake_vec

    monkeypatch.setattr(svc, "_embed_one", fake_embed_one)

    out = await svc.embed_query("hello world")
    assert out == fake_vec
    assert captured.get("set_key", "").startswith("embed:")


@pytest.mark.asyncio
async def test_embed_query_uses_cache(monkeypatch):
    svc = EmbeddingService()
    fake_vec = [0.5] * 768

    async def fake_get(key):
        return json.dumps(fake_vec).encode("utf-8")

    monkeypatch.setattr(svc.cache, "get", fake_get)

    api_called = {"count": 0}

    async def fake_embed_one(text, task_type):
        api_called["count"] += 1
        return fake_vec

    monkeypatch.setattr(svc, "_embed_one", fake_embed_one)

    out = await svc.embed_query("cached query")
    assert out == fake_vec
    assert api_called["count"] == 0


@pytest.mark.asyncio
async def test_embed_batch_returns_list_of_vectors(monkeypatch):
    svc = EmbeddingService()
    by_text = {"a": [0.1] * 768, "b": [0.2] * 768, "c": [0.3] * 768}

    async def fake_embed_one(text, task_type):
        assert task_type == "retrieval_document"
        return by_text[text]

    monkeypatch.setattr(svc, "_embed_one", fake_embed_one)

    out = await svc.embed_batch(["a", "b", "c"])
    assert out == [by_text["a"], by_text["b"], by_text["c"]]
