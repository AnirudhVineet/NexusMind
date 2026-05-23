"""Tests for research brief synthesis — Phase 4 Track B.

Covers: synthesize_brief, ResearchBrief schema, confidence calculation, fallback.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.research import Argument, ResearchBrief
from app.services.research import (
    NoEvidenceError,
    _build_synthesis_prompt,
    _compute_confidence,
    _scrub_arguments,
    synthesize_brief,
)


# ---------------------------------------------------------------------------
# ResearchBrief schema
# ---------------------------------------------------------------------------

class TestResearchBriefSchema:
    """Validate Pydantic schema for research briefs."""

    def test_valid_brief(self):
        brief = ResearchBrief(
            topic="AI",
            executive_summary="AI is transforming industries.",
            key_arguments=[
                Argument(claim="AI improves efficiency", evidence_chunk_ids=["c1"], stance="supporting")
            ],
            evidence_table=[{"chunk_id": "c1", "document_title": "Doc", "key_point": "Point"}],
            counterarguments=[],
            knowledge_gaps=["Limited data on long-term effects"],
            recommended_reading=[{"document_title": "Paper X", "reason": "Foundational"}],
            confidence=0.8,
        )
        assert brief.topic == "AI"
        assert brief.confidence == 0.8
        assert len(brief.key_arguments) == 1

    def test_argument_stance_values(self):
        for stance in ("supporting", "opposing", "neutral"):
            arg = Argument(claim="test", evidence_chunk_ids=[], stance=stance)
            assert arg.stance == stance

    def test_empty_brief(self):
        brief = ResearchBrief(
            topic="Empty",
            executive_summary="",
            key_arguments=[],
            evidence_table=[],
            counterarguments=[],
            knowledge_gaps=[],
            recommended_reading=[],
            confidence=0.0,
        )
        assert brief.confidence == 0.0


# ---------------------------------------------------------------------------
# Confidence calculation
# ---------------------------------------------------------------------------

class TestConfidenceCalculation:
    """Confidence is mean of top-10 similarity scores + small breadth bonus."""

    def test_no_chunks_returns_none(self):
        score, band = _compute_confidence([])
        assert score == 0.0
        assert band == "none"

    def test_low_scores_low_band(self):
        chunks = [
            {"chunk_id": "c1", "document_id": "d1", "score": 0.2},
            {"chunk_id": "c2", "document_id": "d1", "score": 0.25},
        ]
        score, band = _compute_confidence(chunks)
        # Mean of [0.25, 0.2] = 0.225, breadth bonus = 0 (1 unique doc)
        assert score == pytest.approx(0.225)
        assert band == "low"

    def test_breadth_bonus_caps_at_0_1(self):
        chunks = [
            {"chunk_id": f"c{i}", "document_id": f"d{i}", "score": 0.5}
            for i in range(10)
        ]
        score, band = _compute_confidence(chunks)
        # Mean = 0.5, breadth bonus = min(0.1, 9*0.02) = 0.1 → 0.6
        assert score == pytest.approx(0.6)
        assert band == "moderate"

    def test_very_high_band(self):
        chunks = [
            {"chunk_id": f"c{i}", "document_id": f"d{i}", "score": 0.9}
            for i in range(5)
        ]
        score, band = _compute_confidence(chunks)
        assert score >= 0.85
        assert band == "very high"

    def test_score_capped_at_1(self):
        chunks = [
            {"chunk_id": f"c{i}", "document_id": f"d{i}", "score": 1.0}
            for i in range(10)
        ]
        score, _ = _compute_confidence(chunks)
        assert score == 1.0


# ---------------------------------------------------------------------------
# Empty library + scrubbing
# ---------------------------------------------------------------------------

class TestNoEvidence:
    """synthesize_brief should refuse to call the LLM with zero chunks."""

    @pytest.mark.asyncio
    async def test_empty_chunks_raises(self):
        with pytest.raises(NoEvidenceError) as excinfo:
            await synthesize_brief("Anything", [])
        assert "library" in str(excinfo.value).lower()


class TestScrubArguments:
    """Hallucinated chunk_ids must be dropped before the brief is returned."""

    def test_drops_arg_with_no_valid_citations(self):
        out = _scrub_arguments(
            [{"claim": "fake", "evidence_chunk_ids": ["zzz"]}],
            valid_ids={"c1"},
        )
        assert out == []

    def test_keeps_arg_with_at_least_one_valid_citation(self):
        out = _scrub_arguments(
            [{"claim": "real", "evidence_chunk_ids": ["c1", "bogus"]}],
            valid_ids={"c1"},
        )
        assert len(out) == 1
        assert out[0]["evidence_chunk_ids"] == ["c1"]

    def test_handles_none_or_missing(self):
        assert _scrub_arguments(None, valid_ids={"c1"}) == []
        assert _scrub_arguments([], valid_ids={"c1"}) == []
        assert _scrub_arguments(
            [{"claim": "no citations key"}], valid_ids={"c1"}
        ) == []


# ---------------------------------------------------------------------------
# _build_synthesis_prompt
# ---------------------------------------------------------------------------

class TestBuildSynthesisPrompt:
    """Verify prompt construction."""

    def test_contains_topic(self):
        chunks = [{"chunk_id": "c1", "text_content": "Some content", "document_title": "D1"}]
        prompt = _build_synthesis_prompt("Quantum Computing", chunks)
        assert "Quantum Computing" in prompt

    def test_contains_chunk_ids(self):
        chunks = [
            {"chunk_id": "abc123", "text_content": "Text A", "document_title": "Doc A"},
            {"chunk_id": "def456", "text_content": "Text B", "document_title": "Doc B"},
        ]
        prompt = _build_synthesis_prompt("Topic", chunks)
        assert "abc123" in prompt
        assert "def456" in prompt

    def test_text_truncated_at_400(self):
        long_text = "x" * 1000
        chunks = [{"chunk_id": "c1", "text_content": long_text, "document_title": "D"}]
        prompt = _build_synthesis_prompt("Topic", chunks)
        # The chunk text in prompt should be ≤ 400 chars
        # (actual format is "[c1] (D): <text>")
        assert "x" * 401 not in prompt


# ---------------------------------------------------------------------------
# synthesize_brief
# ---------------------------------------------------------------------------

class TestSynthesizeBrief:
    """Test brief synthesis with mocked LLM."""

    @pytest.mark.asyncio
    async def test_groq_success_returns_brief(self):
        import json

        brief_json = json.dumps({
            "topic": "AI",
            "executive_summary": "Summary",
            "key_arguments": [],
            "evidence_table": [],
            "counterarguments": [],
            "knowledge_gaps": [],
            "recommended_reading": [],
            "confidence": 0.5,
        })

        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = brief_json
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

        chunks = [
            {"chunk_id": "c1", "document_id": "d1", "text_content": "Text 1", "score": 0.7},
            {"chunk_id": "c2", "document_id": "d2", "text_content": "Text 2", "score": 0.8},
        ]

        with patch("app.services.research._groq_client", return_value=mock_client):
            brief = await synthesize_brief("AI", chunks)

        assert isinstance(brief, ResearchBrief)
        # Mean(top-10) = 0.75, breadth bonus = 0.02 → 0.77
        assert brief.confidence == pytest.approx(0.77)
        assert brief.evidence_band == "high"
        # evidence_table is overwritten by deterministic builder.
        assert len(brief.evidence_table) == 2
        assert brief.evidence_table[0]["chunk_id"] == "c1"
        assert brief.evidence_table[0]["document_id"] == "d1"

    @pytest.mark.asyncio
    async def test_both_providers_fail_returns_fallback(self):
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("fail"))

        chunks = [
            {"chunk_id": "c1", "document_id": "d1", "text_content": "Text 1", "score": 0.55},
        ]

        with patch("app.services.research._groq_client", return_value=mock_client), \
             patch("app.services.research._ollama_client", return_value=mock_client):
            brief = await synthesize_brief("Fallback Topic", chunks)

        assert isinstance(brief, ResearchBrief)
        assert "failed" in brief.executive_summary.lower() or "unavailable" in brief.executive_summary.lower()
        # Only 1 chunk @ 0.55 → confidence = 0.55, band = "moderate"
        assert brief.confidence == pytest.approx(0.55)
        assert brief.evidence_band == "moderate"
