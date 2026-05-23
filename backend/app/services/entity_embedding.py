"""384-dim entity-similarity embeddings via sentence-transformers/all-MiniLM-L6-v2.

Used only for the entity-dedup cosine check. Chunk embeddings use the
Phase 1 Gemini service (unchanged). Phase 2.5 claim embeddings use bge-base
in a separate service.
"""
from __future__ import annotations

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)


_model = None


def _load_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        settings = get_settings()
        log.info("entity_embedding.loading", model=settings.entity_embedding_model)
        _model = SentenceTransformer(settings.entity_embedding_model)
        log.info("entity_embedding.loaded")
    return _model


def embed_one(text: str) -> list[float]:
    model = _load_model()
    vec = model.encode(text, normalize_embeddings=True)
    return vec.tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = _load_model()
    vecs = model.encode(texts, normalize_embeddings=True, batch_size=32)
    return [v.tolist() for v in vecs]


__all__ = ["embed_one", "embed_batch"]
