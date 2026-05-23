"""Tests for thread generation — Phase 4 Track H.

Covers: generate_thread for twitter/linkedin, char limits, post count.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.services.content_engine import generate_thread


class TestGenerateThread:
    """Test thread generation."""

    _CHUNKS = [
        {"id": "c1", "text_content": "The transformer architecture revolutionized NLP by enabling parallel processing."},
        {"id": "c2", "text_content": "Attention mechanisms allow models to focus on relevant parts of the input."},
    ]

    @pytest.mark.asyncio
    async def test_twitter_thread(self):
        mock_posts = json.dumps([
            {"index": 1, "text": "Thread about transformers 🧵", "source_chunk_id": "c1"},
            {"index": 2, "text": "Attention is all you need.", "source_chunk_id": "c2"},
        ])

        with patch("app.services.content_engine._llm_complete", AsyncMock(return_value=mock_posts)), \
             patch("app.services.content_engine._run_fidelity_checks", AsyncMock(return_value=[])):
            result = await generate_thread(self._CHUNKS, "educational", "twitter")

        content = result["content"]
        assert content["total_posts"] == 2
        assert len(content["posts"]) == 2

    @pytest.mark.asyncio
    async def test_linkedin_thread(self):
        mock_posts = json.dumps([
            {"index": 1, "text": "A long LinkedIn post about AI..." * 10, "source_chunk_id": "c1"},
        ])

        with patch("app.services.content_engine._llm_complete", AsyncMock(return_value=mock_posts)), \
             patch("app.services.content_engine._run_fidelity_checks", AsyncMock(return_value=[])):
            result = await generate_thread(self._CHUNKS, "professional", "linkedin")

        content = result["content"]
        assert content["total_posts"] == 1

    @pytest.mark.asyncio
    async def test_twitter_char_limit_enforced(self):
        long_text = "x" * 500  # exceeds 280 char limit
        mock_posts = json.dumps([
            {"index": 1, "text": long_text, "source_chunk_id": "c1"},
        ])

        with patch("app.services.content_engine._llm_complete", AsyncMock(return_value=mock_posts)), \
             patch("app.services.content_engine._run_fidelity_checks", AsyncMock(return_value=[])):
            result = await generate_thread(self._CHUNKS, "educational", "twitter")

        for post in result["content"]["posts"]:
            assert len(post["text"]) <= 280

    @pytest.mark.asyncio
    async def test_linkedin_char_limit_enforced(self):
        long_text = "y" * 2000  # exceeds 1300 char limit
        mock_posts = json.dumps([
            {"index": 1, "text": long_text, "source_chunk_id": "c1"},
        ])

        with patch("app.services.content_engine._llm_complete", AsyncMock(return_value=mock_posts)), \
             patch("app.services.content_engine._run_fidelity_checks", AsyncMock(return_value=[])):
            result = await generate_thread(self._CHUNKS, "professional", "linkedin")

        for post in result["content"]["posts"]:
            assert len(post["text"]) <= 1300

    @pytest.mark.asyncio
    async def test_invalid_json_fallback(self):
        with patch("app.services.content_engine._llm_complete", AsyncMock(return_value="Not JSON")), \
             patch("app.services.content_engine._run_fidelity_checks", AsyncMock(return_value=[])):
            result = await generate_thread(self._CHUNKS, "educational")

        assert result["content"]["total_posts"] == 1

    @pytest.mark.asyncio
    async def test_default_platform_is_twitter(self):
        mock_posts = json.dumps([
            {"index": 1, "text": "Short post", "source_chunk_id": "c1"},
        ])

        with patch("app.services.content_engine._llm_complete", AsyncMock(return_value=mock_posts)), \
             patch("app.services.content_engine._run_fidelity_checks", AsyncMock(return_value=[])):
            result = await generate_thread(self._CHUNKS, "educational")

        # Should use twitter defaults (280 char limit)
        assert result["content"]["total_posts"] >= 1
