"""Tests for meme generation — Phase 4 Track H.

Covers: generate_meme JSON parsing, _render_meme with Pillow.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.services.content_engine import generate_meme, _render_meme, MEME_TEMPLATES_DIR


class TestGenerateMeme:
    """Test meme generation."""

    _CHUNKS = [
        {"id": "c1", "text_content": "AI is amazing but sometimes overhyped."},
    ]

    @pytest.mark.asyncio
    async def test_successful_generation(self):
        mock_json = json.dumps({
            "template_name": "Drake",
            "top_text": "Using traditional methods",
            "bottom_text": "Using AI for everything",
            "alt_panel_texts": [],
            "caption": "AI meme",
            "source_chunk_id": "c1",
        })

        with patch("app.services.content_engine._llm_complete", AsyncMock(return_value=mock_json)), \
             patch("app.services.content_engine._run_fidelity_checks", AsyncMock(return_value=[])):
            result = await generate_meme(self._CHUNKS, "humorous")

        assert "content" in result
        assert result["content"]["template_name"] == "Drake"
        assert "fidelity_flags" in result

    @pytest.mark.asyncio
    async def test_invalid_json_fallback(self):
        with patch("app.services.content_engine._llm_complete", AsyncMock(return_value="Random text")), \
             patch("app.services.content_engine._run_fidelity_checks", AsyncMock(return_value=[])):
            result = await generate_meme(self._CHUNKS, "humorous")

        assert result["content"]["template_name"] == "Drake"


class TestRenderMeme:
    """Test Pillow-based meme rendering."""

    def test_render_with_no_template_returns_none(self, tmp_path):
        # Non-existent template path
        result = _render_meme(
            template_path=tmp_path / "nonexistent.png",
            top_text="Top",
            bottom_text="Bottom",
        )
        assert result is None

    def test_render_with_valid_template(self, tmp_path):
        """Create a minimal PNG and render text on it."""
        from PIL import Image

        template = tmp_path / "test.png"
        img = Image.new("RGBA", (400, 400), (255, 255, 255, 255))
        img.save(str(template))

        with patch("app.services.content_engine.get_settings") as mock_settings:
            mock_settings.return_value.storage_dir = str(tmp_path / "data")
            result = _render_meme(
                template_path=template,
                top_text="Top text",
                bottom_text="Bottom text",
            )

        assert result is not None
        assert result.endswith(".png")
        assert Path(result).exists()

    def test_render_with_empty_text(self, tmp_path):
        """Empty text should not crash."""
        from PIL import Image

        template = tmp_path / "test.png"
        img = Image.new("RGBA", (200, 200), (0, 0, 0, 255))
        img.save(str(template))

        with patch("app.services.content_engine.get_settings") as mock_settings:
            mock_settings.return_value.storage_dir = str(tmp_path / "data")
            result = _render_meme(
                template_path=template,
                top_text="",
                bottom_text="",
            )

        # Should succeed even with empty text
        assert result is not None
