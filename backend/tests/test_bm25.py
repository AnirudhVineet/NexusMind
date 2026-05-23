"""Tests for BM25 retrieval path."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_bm25_search_returns_ranked_results():
    """bm25_search executes ts_rank_cd query and returns (chunk_id, score) pairs."""
    from app.services.retrieval import bm25_search

    mock_row1 = {"chunk_id": str(uuid.uuid4()), "score": 0.9}
    mock_row2 = {"chunk_id": str(uuid.uuid4()), "score": 0.4}

    mock_mappings = MagicMock()
    mock_mappings.all.return_value = [mock_row1, mock_row2]
    mock_result = MagicMock()
    mock_result.mappings.return_value = mock_mappings

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    user_id = uuid.uuid4()
    results = await bm25_search(mock_session, user_id, query="machine learning", top_k=10)

    assert len(results) == 2
    chunk_id_1, score_1 = results[0]
    assert isinstance(chunk_id_1, uuid.UUID)
    assert score_1 == pytest.approx(0.9)


@pytest.mark.asyncio
async def test_bm25_search_empty_results():
    """bm25_search returns empty list when no BM25 matches found."""
    from app.services.retrieval import bm25_search

    mock_mappings = MagicMock()
    mock_mappings.all.return_value = []
    mock_result = MagicMock()
    mock_result.mappings.return_value = mock_mappings

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    results = await bm25_search(mock_session, uuid.uuid4(), query="xyznotaword", top_k=10)
    assert results == []


@pytest.mark.asyncio
async def test_bm25_applies_source_type_filter():
    """bm25_search SQL includes source_type filter when provided."""
    from app.services.retrieval import SearchFilters, bm25_search

    mock_mappings = MagicMock()
    mock_mappings.all.return_value = []
    mock_result = MagicMock()
    mock_result.mappings.return_value = mock_mappings

    captured_sql = []

    async def capture_execute(stmt, params=None):
        captured_sql.append(str(stmt))
        return mock_result

    mock_session = AsyncMock()
    mock_session.execute = capture_execute

    filters = SearchFilters(source_type="pdf")
    await bm25_search(
        mock_session, uuid.uuid4(), query="test", top_k=10, filters=filters
    )

    assert len(captured_sql) == 1
    assert "source_type" in captured_sql[0]
