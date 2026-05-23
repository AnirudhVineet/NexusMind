"""Track B — Brief narration chapter splitter."""
from __future__ import annotations

from app.services.media.brief_narration import split_brief_into_chapters


def test_splitter_includes_summary_and_arguments():
    bjson = {
        "topic": "Quantum entanglement",
        "executive_summary": "Quantum entanglement is real.",
        "key_arguments": [
            {"claim": "Bell tests confirm it.", "stance": "supporting"},
            {"claim": "Loopholes have been closed.", "stance": "supporting"},
        ],
        "counterarguments": [
            {"claim": "Some interpretations differ."},
        ],
        "knowledge_gaps": ["More large-distance tests needed"],
        "recommended_reading": [{"title": "Aspect 1982"}],
    }
    chapters = split_brief_into_chapters(bjson)
    headings = [c.heading for c in chapters]
    assert any("Executive Summary" in h for h in headings)
    assert any("Argument 1" in h for h in headings)
    assert any("Counterargument 1" in h for h in headings)
    assert any("Knowledge Gaps" in h for h in headings)
    assert any("Recommended Reading" in h for h in headings)


def test_splitter_skips_empty_sections():
    chapters = split_brief_into_chapters({"executive_summary": "Just this."})
    assert len(chapters) == 1
    assert "Executive Summary" in chapters[0].heading


def test_splitter_handles_plain_string_arguments():
    bjson = {
        "key_arguments": ["A claim with no structure"],
    }
    chapters = split_brief_into_chapters(bjson)
    assert len(chapters) == 1
    assert "Argument 1" in chapters[0].heading
    assert chapters[0].text == "A claim with no structure"


def test_splitter_returns_empty_on_empty_brief():
    chapters = split_brief_into_chapters({})
    assert chapters == []
