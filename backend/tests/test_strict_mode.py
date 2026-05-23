"""Tests for strict mode fidelity — Phase 4 Track H.

Covers: strict_mode raises fidelity threshold to 0.85.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.content_engine import check_source_fidelity


class TestStrictMode:
    """Verify strict_mode raises the fidelity threshold to 0.85."""

    @pytest.mark.asyncio
    async def test_strict_mode_threshold(self):
        claim_vec = [1.0, 0.0, 0.0]
        source_vec = [0.8, 0.2, 0.0]  # sim ~ 0.97 — passes both

        mock_svc = MagicMock()
        mock_svc.embed_batch = AsyncMock(return_value=[claim_vec])

        with patch("app.services.content_engine.get_embedding_service", return_value=mock_svc):
            normal = await check_source_fidelity("claim", [{"id": "c1", "embedding": source_vec}], strict_mode=False)
            strict = await check_source_fidelity("claim", [{"id": "c1", "embedding": source_vec}], strict_mode=True)

        assert normal["pass"] is True
        assert strict["pass"] is True  # high sim passes both

    @pytest.mark.asyncio
    async def test_strict_mode_fails_moderate_sim(self):
        """A similarity of ~0.78 passes normal (0.75) but fails strict (0.85)."""
        claim_vec = [1.0, 0.0]
        source_vec = [0.78, 0.63]  # cosine sim ≈ 0.78

        mock_svc = MagicMock()
        mock_svc.embed_batch = AsyncMock(return_value=[claim_vec])

        with patch("app.services.content_engine.get_embedding_service", return_value=mock_svc):
            normal = await check_source_fidelity("claim", [{"id": "c1", "embedding": source_vec}], strict_mode=False)
            strict = await check_source_fidelity("claim", [{"id": "c1", "embedding": source_vec}], strict_mode=True)

        assert normal["pass"] is True
        assert strict["pass"] is False

    @pytest.mark.asyncio
    async def test_explicit_threshold_overrides_strict(self):
        """An explicit threshold takes precedence over strict_mode."""
        claim_vec = [1.0, 0.0]
        source_vec = [0.9, 0.1]

        mock_svc = MagicMock()
        mock_svc.embed_batch = AsyncMock(return_value=[claim_vec])

        with patch("app.services.content_engine.get_embedding_service", return_value=mock_svc):
            result = await check_source_fidelity(
                "claim", [{"id": "c1", "embedding": source_vec}],
                threshold=0.5, strict_mode=True,
            )

        # Explicit threshold=0.5 used, not strict 0.85
        assert result["pass"] is True
