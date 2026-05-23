import asyncio
import hashlib
import json
from functools import lru_cache

import google.generativeai as genai
import redis.asyncio as redis_async
from prometheus_client import Counter
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)

EMBEDDING_REQUESTS = Counter(
    "embedding_requests_total",
    "Total embedding requests",
    ["mode"],
)
EMBEDDING_CHUNKS = Counter(
    "embedding_chunks_total",
    "Total chunks (or queries) embedded",
)


@lru_cache
def _redis() -> redis_async.Redis:
    return redis_async.from_url(get_settings().redis_url, decode_responses=False)


_gemini_configured = False


def _ensure_gemini() -> None:
    global _gemini_configured
    if _gemini_configured:
        return
    genai.configure(api_key=get_settings().gemini_api_key)
    _gemini_configured = True


def _truncate(text: str, max_chars: int = 32_000) -> str:
    text = text.strip()
    return text[:max_chars]


def _cache_key(text: str, model: str, task: str) -> str:
    h = hashlib.sha256(f"{model}:{task}:{text}".encode("utf-8")).hexdigest()
    return f"embed:{h}"


class EmbeddingService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.model = self.settings.embedding_model
        self.model_path = (
            self.model if self.model.startswith("models/") else f"models/{self.model}"
        )
        self.cache = _redis()
        self.cache_ttl = 60 * 60 * 24  # 24h
        _ensure_gemini()

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        reraise=True,
    )
    async def _embed_one(self, text: str, task_type: str) -> list[float]:
        # gemini-embedding-001 only supports the singular embedContent endpoint.
        # Always pass a single string so the SDK uses that path.
        def _do():
            return genai.embed_content(
                model=self.model_path,
                content=text,
                task_type=task_type,
                output_dimensionality=self.settings.embedding_dim,
            )

        result = await asyncio.to_thread(_do)
        return result["embedding"]

    async def embed_query(self, text: str) -> list[float]:
        EMBEDDING_REQUESTS.labels(mode="query").inc()
        text = _truncate(text)
        key = _cache_key(text, self.model, "query")

        try:
            cached = await self.cache.get(key)
            if cached:
                return json.loads(cached)
        except Exception:
            log.warning("embedding_cache_read_failed")

        vec = await self._embed_one(text, "retrieval_query")
        EMBEDDING_CHUNKS.inc()

        try:
            await self.cache.set(key, json.dumps(vec), ex=self.cache_ttl)
        except Exception:
            log.warning("embedding_cache_write_failed")
        return vec

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        EMBEDDING_REQUESTS.labels(mode="batch").inc()
        if not texts:
            return []
        truncated = [_truncate(t) for t in texts]
        sem = asyncio.Semaphore(8)

        async def _one(t: str) -> list[float]:
            async with sem:
                return await self._embed_one(t, "retrieval_document")

        out = await asyncio.gather(*(_one(t) for t in truncated))
        EMBEDDING_CHUNKS.inc(len(out))
        return out


def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()


def embed_batch_sync(texts: list[str]) -> list[list[float]]:
    """Sync wrapper for Celery workers."""
    svc = EmbeddingService()
    return asyncio.run(svc.embed_batch(texts))
