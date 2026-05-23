"""Tests for tone classification — Phase 4 Track H.

Covers: classify_tone with mocked LLM, valid output set.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.content_engine import classify_tone


class TestClassifyTone:
    """Test tone classification."""

    _CHUNKS = [
        {"text_content": "The algorithm achieves O(n log n) complexity using a divide-and-conquer approach."},
    ]

    @pytest.mark.asyncio
    async def test_returns_valid_tone(self):
        with patch("app.services.content_engine._groq_complete", AsyncMock(return_value="technical")):
            result = await classify_tone(self._CHUNKS)
        assert result in {"technical", "narrative", "opinionated", "data-heavy"}

    @pytest.mark.asyncio
    async def test_narrative_tone(self):
        with patch("app.services.content_engine._groq_complete", AsyncMock(return_value="narrative")):
            result = await classify_tone(self._CHUNKS)
        assert result == "narrative"

    @pytest.mark.asyncio
    async def test_invalid_tone_defaults_to_technical(self):
        with patch("app.services.content_engine._groq_complete", AsyncMock(return_value="unknown_tone")):
            result = await classify_tone(self._CHUNKS)
        assert result == "technical"

    @pytest.mark.asyncio
    async def test_empty_response_defaults_to_technical(self):
        with patch("app.services.content_engine._groq_complete", AsyncMock(return_value="")):
            result = await classify_tone(self._CHUNKS)
        assert result == "technical"

    @pytest.mark.asyncio
    async def test_exception_defaults_to_technical(self):
        with patch("app.services.content_engine._groq_complete", AsyncMock(side_effect=Exception("API error"))):
            result = await classify_tone(self._CHUNKS)
        assert result == "technical"

    @pytest.mark.asyncio
    async def test_multi_word_response_takes_first(self):
        with patch("app.services.content_engine._groq_complete", AsyncMock(return_value="narrative tone")):
            result = await classify_tone(self._CHUNKS)
        assert result == "narrative"
