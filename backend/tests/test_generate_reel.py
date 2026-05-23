"""Tests for reel script generation — Phase 4 Track H.

Covers: generate_reel_script with mocked LLM, output structure.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.services.content_engine import generate_reel_script


class TestGenerateReelScript:
    """Test reel script generation."""

    _CHUNKS = [
        {"id": "c1", "text_content": "AI transforms healthcare diagnostics."},
        {"id": "c2", "text_content": "Deep learning enables image classification."},
    ]

    @pytest.mark.asyncio
    async def test_successful_generation(self):
        mock_json = json.dumps({
            "hook": "Did you know AI can diagnose diseases?",
            "beats": [
                {"text": "Beat 1 text", "source_chunk_id": "c1"},
                {"text": "Beat 2 text", "source_chunk_id": "c2"},
            ],
            "cta": "Follow for more AI content",
            "caption": "AI in healthcare #ai",
            "hashtags": ["#ai", "#healthcare"],
        })

        with patch("app.services.content_engine._llm_complete", AsyncMock(return_value=mock_json)), \
             patch("app.services.content_engine._run_fidelity_checks", AsyncMock(return_value=[])):
            result = await generate_reel_script(self._CHUNKS, "educational")

        assert "content" in result
        assert "fidelity_flags" in result
        content = result["content"]
        assert "hook" in content
        assert "beats" in content
        assert len(content["beats"]) == 2

    @pytest.mark.asyncio
    async def test_invalid_json_fallback(self):
        with patch("app.services.content_engine._llm_complete", AsyncMock(return_value="Not JSON")), \
             patch("app.services.content_engine._run_fidelity_checks", AsyncMock(return_value=[])):
            result = await generate_reel_script(self._CHUNKS, "educational")

        assert "content" in result
        # Fallback content should have hook = raw text
        assert result["content"]["beats"] == []

    @pytest.mark.asyncio
    async def test_fidelity_flags_included(self):
        mock_json = json.dumps({
            "hook": "Hook",
            "beats": [{"text": "Beat", "source_chunk_id": "c1"}],
            "cta": "CTA",
            "caption": "Caption",
            "hashtags": [],
        })
        mock_flags = [{"label": "beat_0", "pass": True, "max_sim": 0.8, "best_source_chunk_id": "c1"}]

        with patch("app.services.content_engine._llm_complete", AsyncMock(return_value=mock_json)), \
             patch("app.services.content_engine._run_fidelity_checks", AsyncMock(return_value=mock_flags)):
            result = await generate_reel_script(self._CHUNKS, "educational")

        assert len(result["fidelity_flags"]) == 1
