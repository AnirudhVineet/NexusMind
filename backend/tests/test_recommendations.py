"""Tests for document recommendation scoring — Phase 4 Track A.

Pure logic tests for recommendation scoring algorithm:
- Score = sum(interest_weight × topic_confidence) per document
- Exclude already-viewed documents
- Limit and sort
"""
import uuid

import pytest


def _score_docs(
    distribution: dict[str, float],
    docs: list[dict],
    viewed_ids: set[str],
    limit: int = 10,
) -> list[dict]:
    """Simulate recommendation scoring logic from memory.py without DB access."""
    scored = []
    for doc in docs:
        if doc["id"] in viewed_ids:
            continue
        score = 0.0
        matched = []
        for slug, confidence in doc.get("tags", []):
            interest = distribution.get(slug, 0.0)
            if interest > 0:
                score += interest * confidence
                matched.append(slug)
        if score > 0:
            scored.append({
                "id": doc["id"],
                "title": doc["title"],
                "score": score,
                "matched_topics": matched,
            })
    scored.sort(key=lambda d: d["score"], reverse=True)
    return scored[:limit]


class TestRecommendationScoring:
    """Verify document recommendation logic."""

    def _doc(self, title: str, tags: list[tuple[str, float]]) -> dict:
        return {"id": str(uuid.uuid4()), "title": title, "tags": tags}

    def test_basic_scoring(self):
        dist = {"ai": 0.6, "math": 0.4}
        docs = [self._doc("AI paper", [("ai", 0.9)]), self._doc("Math textbook", [("math", 0.8)])]
        recs = _score_docs(dist, docs, set())
        assert recs[0]["title"] == "AI paper"  # 0.6*0.9 = 0.54 > 0.4*0.8 = 0.32

    def test_viewed_docs_excluded(self):
        dist = {"ai": 0.6}
        doc = self._doc("Viewed", [("ai", 1.0)])
        recs = _score_docs(dist, [doc], {doc["id"]})
        assert recs == []

    def test_unmatched_topics_score_zero(self):
        dist = {"ai": 0.6}
        doc = self._doc("No match", [("history", 0.9)])
        recs = _score_docs(dist, [doc], set())
        assert recs == []

    def test_limit_parameter(self):
        dist = {"ai": 0.5}
        docs = [self._doc(f"Doc {i}", [("ai", 0.5)]) for i in range(20)]
        recs = _score_docs(dist, docs, set(), limit=5)
        assert len(recs) == 5

    def test_multi_topic_score_aggregation(self):
        dist = {"ai": 0.3, "math": 0.3, "physics": 0.4}
        doc = self._doc("Cross", [("ai", 0.5), ("math", 0.5), ("physics", 0.5)])
        recs = _score_docs(dist, [doc], set())
        expected_score = 0.3 * 0.5 + 0.3 * 0.5 + 0.4 * 0.5  # 0.5
        assert recs[0]["score"] == pytest.approx(expected_score)

    def test_empty_distribution_returns_nothing(self):
        docs = [self._doc("Something", [("ai", 1.0)])]
        recs = _score_docs({}, docs, set())
        assert recs == []

    def test_empty_docs_returns_empty(self):
        recs = _score_docs({"ai": 0.5}, [], set())
        assert recs == []

    def test_sorted_by_score_descending(self):
        dist = {"ai": 0.5}
        docs = [
            self._doc("Low", [("ai", 0.1)]),
            self._doc("High", [("ai", 0.9)]),
            self._doc("Mid", [("ai", 0.5)]),
        ]
        recs = _score_docs(dist, docs, set())
        scores = [r["score"] for r in recs]
        assert scores == sorted(scores, reverse=True)

    def test_matched_topics_populated(self):
        dist = {"ai": 0.5, "math": 0.3}
        doc = self._doc("Multi", [("ai", 0.8), ("math", 0.6), ("history", 0.2)])
        recs = _score_docs(dist, [doc], set())
        assert set(recs[0]["matched_topics"]) == {"ai", "math"}
