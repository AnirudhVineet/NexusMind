"""Tests for reranker — uses mocked CrossEncoder."""
import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.services.retrieval import RetrievalHit


def _make_hit(text: str, score: float = 0.5) -> RetrievalHit:
    return RetrievalHit(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_title="test.pdf",
        page_number=1,
        section=None,
        text=text,
        similarity_score=score,
    )


def test_rerank_changes_order_for_misranked_input():
    """Reranker should reorder hits based on CrossEncoder scores."""
    from app.services import retrieval as ret_module

    hits = [
        _make_hit("Irrelevant text about cooking recipes"),
        _make_hit("Machine learning is a subset of artificial intelligence"),
        _make_hit("Another irrelevant paragraph about gardening"),
    ]

    # Mock CrossEncoder to give highest score to the second hit
    mock_encoder = MagicMock()
    mock_encoder.predict.return_value = [0.1, 0.95, 0.05]

    with patch.object(ret_module, "_reranker", mock_encoder):
        result = ret_module.rerank("what is machine learning?", hits, top_k=2)

    assert len(result) == 2
    assert result[0].text == "Machine learning is a subset of artificial intelligence"


def test_rerank_respects_top_k():
    from app.services import retrieval as ret_module

    hits = [_make_hit(f"chunk {i}") for i in range(10)]
    mock_encoder = MagicMock()
    mock_encoder.predict.return_value = list(range(10, 0, -1))

    with patch.object(ret_module, "_reranker", mock_encoder):
        result = ret_module.rerank("query", hits, top_k=3)

    assert len(result) == 3


def test_rerank_disabled_via_config():
    """When RERANKER_ENABLED=false, rerank returns top_k in original order."""
    from app.services.retrieval import rerank

    hits = [_make_hit(f"chunk {i}") for i in range(5)]
    with patch("app.services.retrieval.get_settings") as mock_settings:
        mock_settings.return_value.reranker_enabled = False
        mock_settings.return_value.reranker_model = "BAAI/bge-reranker-base"
        result = rerank("query", hits, top_k=3)

    assert result == hits[:3]


def test_rerank_empty_hits():
    from app.services.retrieval import rerank

    result = rerank("query", [], top_k=5)
    assert result == []
