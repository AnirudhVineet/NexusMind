"""Tests for source fidelity checking — Phase 4 Track H.

Covers: _cosine helper, check_source_fidelity with known embeddings, threshold.
"""
from __future__ import annotations

import math
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.content_engine import (
    FIDELITY_THRESHOLD_DEFAULT,
    _cosine,
    _fidelity_threshold,
    check_source_fidelity,
)


class TestCosineHelper:
    """Test the cosine similarity helper in content_engine."""

    def test_identical_vectors(self):
        v = [1.0, 2.0, 3.0]
        assert _cosine(v, v) == pytest.approx(1.0, abs=1e-6)

    def test_orthogonal(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert _cosine(a, b) == pytest.approx(0.0, abs=1e-6)

    def test_zero_vector(self):
        assert _cosine([0.0, 0.0], [1.0, 2.0]) == 0.0


class TestFidelityThreshold:
    """Test threshold configuration."""

    def test_default_threshold(self):
        assert FIDELITY_THRESHOLD_DEFAULT == 0.75

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("CONTENT_FIDELITY_THRESHOLD", "0.80")
        assert _fidelity_threshold() == 0.80

    def test_invalid_env_falls_back(self, monkeypatch):
        monkeypatch.setenv("CONTENT_FIDELITY_THRESHOLD", "not-a-number")
        assert _fidelity_threshold() == FIDELITY_THRESHOLD_DEFAULT

    def test_empty_env_uses_default(self, monkeypatch):
        monkeypatch.setenv("CONTENT_FIDELITY_THRESHOLD", "")
        assert _fidelity_threshold() == FIDELITY_THRESHOLD_DEFAULT


class TestCheckSourceFidelity:
    """Test fidelity check with known embeddings."""

    @pytest.mark.asyncio
    async def test_high_similarity_passes(self):
        claim_vec = [1.0, 0.0, 0.0]
        source_vec = [0.99, 0.1, 0.0]  # very similar

        mock_svc = MagicMock()
        mock_svc.embed_batch = AsyncMock(return_value=[claim_vec])

        with patch("app.services.content_engine.get_embedding_service", return_value=mock_svc):
            result = await check_source_fidelity(
                "Test claim",
                [{"id": "c1", "embedding": source_vec}],
                threshold=0.5,
            )

        assert result["pass"] is True
        assert result["max_sim"] > 0.5
        assert result["best_source_chunk_id"] == "c1"

    @pytest.mark.asyncio
    async def test_low_similarity_fails(self):
        claim_vec = [1.0, 0.0, 0.0]
        source_vec = [0.0, 1.0, 0.0]  # orthogonal

        mock_svc = MagicMock()
        mock_svc.embed_batch = AsyncMock(return_value=[claim_vec])

        with patch("app.services.content_engine.get_embedding_service", return_value=mock_svc):
            result = await check_source_fidelity(
                "Test claim",
                [{"id": "c1", "embedding": source_vec}],
                threshold=0.5,
            )

        assert result["pass"] is False
        assert result["max_sim"] < 0.5

    @pytest.mark.asyncio
    async def test_no_embeddings_returns_zero(self):
        mock_svc = MagicMock()
        mock_svc.embed_batch = AsyncMock(return_value=[[1.0, 0.0]])

        with patch("app.services.content_engine.get_embedding_service", return_value=mock_svc):
            result = await check_source_fidelity(
                "Test",
                [{"id": "c1"}],  # no embedding
            )

        assert result["pass"] is False
        assert result["max_sim"] == 0.0

    @pytest.mark.asyncio
    async def test_best_chunk_selected(self):
        claim_vec = [1.0, 0.0]
        chunks = [
            {"id": "c1", "embedding": [0.0, 1.0]},  # low sim
            {"id": "c2", "embedding": [0.95, 0.1]},  # high sim
            {"id": "c3", "embedding": [0.5, 0.5]},   # medium
        ]

        mock_svc = MagicMock()
        mock_svc.embed_batch = AsyncMock(return_value=[claim_vec])

        with patch("app.services.content_engine.get_embedding_service", return_value=mock_svc):
            result = await check_source_fidelity("Test", chunks, threshold=0.5)

        assert result["best_source_chunk_id"] == "c2"
