"""Tests for evidence gathering — Phase 4 Track B.

Covers: chunk deduplication, provenance tracking, empty query handling.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.research import gather_evidence


class _FakeHit:
    """Minimal retrieval hit for testing."""

    def __init__(self, chunk_id: uuid.UUID, doc_id: uuid.UUID, text: str, score: float):
        self.chunk_id = chunk_id
        self.document_id = doc_id
        self.document_title = f"Doc-{doc_id.hex[:6]}"
        self.text = text
        self.similarity_score = score
        self.source_type = "upload"


class TestGatherEvidence:
    """Test evidence gathering from hybrid search results."""

    def _make_hits(self, n: int, shared_id: uuid.UUID | None = None) -> list[_FakeHit]:
        hits = []
        for i in range(n):
            cid = shared_id if shared_id and i == 0 else uuid.uuid4()
            hits.append(_FakeHit(cid, uuid.uuid4(), f"Text {i}", 0.9 - i * 0.1))
        return hits

    @pytest.mark.asyncio
    async def test_deduplicates_chunk_ids(self):
        shared_id = uuid.uuid4()
        hits_q1 = [_FakeHit(shared_id, uuid.uuid4(), "Chunk A", 0.9)]
        hits_q2 = [_FakeHit(shared_id, uuid.uuid4(), "Chunk A dup", 0.85)]

        mock_embedder = MagicMock()
        mock_embedder.embed_query = AsyncMock(return_value=[0.1] * 768)

        async def _fake_search(session, user_id, query, query_vec, top_k, filters):
            if "q1" in query:
                return hits_q1
            return hits_q2

        with patch("app.services.research.get_embedding_service", return_value=mock_embedder), \
             patch("app.services.research.hybrid_search", side_effect=_fake_search):
            results = await gather_evidence(
                ["q1", "q2"],
                uuid.uuid4(),
                AsyncMock(),
            )

        chunk_ids = [r["chunk_id"] for r in results]
        assert len(chunk_ids) == len(set(chunk_ids)), "Duplicate chunk_ids found"

    @pytest.mark.asyncio
    async def test_provenance_tracked(self):
        hit = _FakeHit(uuid.uuid4(), uuid.uuid4(), "Text", 0.9)

        mock_embedder = MagicMock()
        mock_embedder.embed_query = AsyncMock(return_value=[0.1] * 768)

        with patch("app.services.research.get_embedding_service", return_value=mock_embedder), \
             patch("app.services.research.hybrid_search", AsyncMock(return_value=[hit])):
            results = await gather_evidence(["What is AI?"], uuid.uuid4(), AsyncMock())

        assert results[0]["provenance"] == "What is AI?"

    @pytest.mark.asyncio
    async def test_empty_query_list_returns_empty(self):
        mock_embedder = MagicMock()
        mock_embedder.embed_query = AsyncMock(return_value=[0.1] * 768)

        with patch("app.services.research.get_embedding_service", return_value=mock_embedder), \
             patch("app.services.research.hybrid_search", AsyncMock(return_value=[])):
            results = await gather_evidence([], uuid.uuid4(), AsyncMock())

        assert results == []

    @pytest.mark.asyncio
    async def test_search_failure_is_swallowed(self):
        mock_embedder = MagicMock()
        mock_embedder.embed_query = AsyncMock(side_effect=Exception("embed error"))

        with patch("app.services.research.get_embedding_service", return_value=mock_embedder):
            results = await gather_evidence(["q1"], uuid.uuid4(), AsyncMock())

        assert results == []
