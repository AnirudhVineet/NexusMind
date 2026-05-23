"""Tests for Phase 3.3 multi-source ingestion services."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock


# ─── Web scraper ──────────────────────────────────────────────────────────────

def test_extract_text_returns_title_and_body():
    from app.services.web_scraper import _extract_text

    html = """
    <html><head><title>Test Page</title></head>
    <body>
      <nav>skip me</nav>
      <main><p>Hello world content here.</p></main>
      <footer>skip me too</footer>
    </body></html>
    """
    title, text = _extract_text(html)
    assert title == "Test Page"
    assert "Hello world content here" in text
    assert "skip me" not in text


def test_extract_text_falls_back_to_body():
    from app.services.web_scraper import _extract_text

    html = "<html><body><p>Just a paragraph.</p></body></html>"
    _, text = _extract_text(html)
    assert "Just a paragraph" in text


# ─── YouTube ingest ───────────────────────────────────────────────────────────

def test_extract_video_id_standard_url():
    from app.services.youtube_ingest import _extract_video_id

    assert _extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_extract_video_id_short_url():
    from app.services.youtube_ingest import _extract_video_id

    assert _extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_extract_video_id_invalid():
    from app.services.youtube_ingest import _extract_video_id

    assert _extract_video_id("https://example.com") is None


def test_fetch_transcript_invalid_url():
    from app.services.youtube_ingest import fetch_transcript

    with pytest.raises(ValueError, match="Cannot extract YouTube video ID"):
        fetch_transcript("https://example.com/not-a-youtube-url")


# ─── Notion ingest ────────────────────────────────────────────────────────────

def test_rich_text_to_str():
    from app.services.notion_ingest import _rich_text_to_str

    rich_text = [
        {"plain_text": "Hello "},
        {"plain_text": "world"},
    ]
    assert _rich_text_to_str(rich_text) == "Hello world"


def test_block_to_text_paragraph():
    from app.services.notion_ingest import _block_to_text

    block = {
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"plain_text": "Some paragraph text."}]
        },
    }
    assert _block_to_text(block) == "Some paragraph text."


def test_block_to_text_heading():
    from app.services.notion_ingest import _block_to_text

    block = {
        "type": "heading_2",
        "heading_2": {
            "rich_text": [{"plain_text": "Section Title"}]
        },
    }
    assert _block_to_text(block) == "## Section Title"


def test_block_to_text_unsupported_returns_empty():
    from app.services.notion_ingest import _block_to_text

    block = {"type": "image", "image": {}}
    assert _block_to_text(block) == ""
