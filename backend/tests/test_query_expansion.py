"""Tests for query expansion — Phase 4 Track B.

Covers: expand_query with mocked LLM, fallback behaviour, JSON parsing.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.research import _coerce_json, expand_query


# ---------------------------------------------------------------------------
# _coerce_json helper
# ---------------------------------------------------------------------------

class TestCoerceJson:
    """JSON extraction helper used by multiple research functions."""

    def test_valid_json_array(self):
        assert _coerce_json('["a", "b"]') == ["a", "b"]

    def test_valid_json_object(self):
        assert _coerce_json('{"key": "value"}') == {"key": "value"}

    def test_json_embedded_in_prose(self):
        text = 'Here are the questions:\n["q1", "q2", "q3"]\nEnd.'
        result = _coerce_json(text)
        assert result == ["q1", "q2", "q3"]

    def test_markdown_fenced_json(self):
        text = '```json\n{"a": 1}\n```'
        result = _coerce_json(text)
        assert result == {"a": 1}

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="empty"):
            _coerce_json("")

    def test_pure_prose_raises(self):
        with pytest.raises(Exception):
            _coerce_json("This is just plain text with no JSON.")


# ---------------------------------------------------------------------------
# expand_query
# ---------------------------------------------------------------------------

class TestExpandQuery:
    """Test query expansion with mocked LLM calls."""

    @pytest.mark.asyncio
    async def test_groq_success(self):
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = '["What is X?", "How does X work?", "Who uses X?"]'

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

        with patch("app.services.research._groq_client", return_value=mock_client):
            result = await expand_query("Machine Learning", n=3)

        assert len(result) == 3
        assert all(isinstance(q, str) for q in result)

    @pytest.mark.asyncio
    async def test_groq_fails_ollama_succeeds(self):
        mock_groq = AsyncMock()
        mock_groq.chat.completions.create = AsyncMock(side_effect=Exception("rate limit"))

        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = '["q1", "q2"]'
        mock_ollama = AsyncMock()
        mock_ollama.chat.completions.create = AsyncMock(return_value=mock_resp)

        with patch("app.services.research._groq_client", return_value=mock_groq), \
             patch("app.services.research._ollama_client", return_value=mock_ollama):
            result = await expand_query("AI", n=2)

        assert result == ["q1", "q2"]

    @pytest.mark.asyncio
    async def test_both_fail_returns_original_topic(self):
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("down"))

        with patch("app.services.research._groq_client", return_value=mock_client), \
             patch("app.services.research._ollama_client", return_value=mock_client):
            result = await expand_query("Quantum Computing")

        assert result == ["Quantum Computing"]
