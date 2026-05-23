"""Tests for knowledge gap detection — Phase 4 Track A.

Pure logic tests for gap-detection criteria: weight threshold, coverage
threshold, sorting, and top-10 capping.
"""
import pytest


def _compute_gaps(distribution: dict, coverage_map: dict, weight_threshold: float = 0.03) -> list[dict]:
    """Simulate the gap detection logic from memory.py without DB access."""
    gaps = []
    for slug, weight in distribution.items():
        if weight <= weight_threshold:
            continue
        coverage = coverage_map.get(slug, 0)
        if coverage < 3:
            gaps.append({
                "topic": slug,
                "display_name": slug,
                "weight": weight,
                "coverage_count": coverage,
            })
    gaps.sort(key=lambda g: g["weight"], reverse=True)
    return gaps[:10]


class TestGapDetection:
    """Verify knowledge gap identification logic."""

    def test_low_coverage_is_a_gap(self):
        distribution = {"ai": 0.5, "math": 0.3, "history": 0.2}
        coverage = {"ai": 1, "math": 5, "history": 2}
        gaps = _compute_gaps(distribution, coverage)
        topic_names = [g["topic"] for g in gaps]
        assert "ai" in topic_names
        assert "history" in topic_names
        assert "math" not in topic_names  # coverage >= 3

    def test_low_weight_topics_are_excluded(self):
        distribution = {"ai": 0.5, "tiny": 0.02}
        coverage = {"ai": 1, "tiny": 0}
        gaps = _compute_gaps(distribution, coverage)
        assert len(gaps) == 1
        assert gaps[0]["topic"] == "ai"

    def test_sorted_by_weight_descending(self):
        distribution = {"c": 0.1, "a": 0.5, "b": 0.3}
        coverage = {"c": 0, "a": 0, "b": 0}
        gaps = _compute_gaps(distribution, coverage)
        weights = [g["weight"] for g in gaps]
        assert weights == sorted(weights, reverse=True)

    def test_capped_at_ten(self):
        distribution = {f"t{i}": 0.1 for i in range(20)}
        coverage = {f"t{i}": 0 for i in range(20)}
        gaps = _compute_gaps(distribution, coverage)
        assert len(gaps) == 10

    def test_empty_distribution_returns_no_gaps(self):
        gaps = _compute_gaps({}, {})
        assert gaps == []

    def test_all_topics_well_covered_returns_empty(self):
        distribution = {"ai": 0.5, "math": 0.5}
        coverage = {"ai": 10, "math": 5}
        gaps = _compute_gaps(distribution, coverage)
        assert gaps == []

    def test_zero_coverage_is_a_gap(self):
        distribution = {"ai": 0.5}
        coverage = {"ai": 0}
        gaps = _compute_gaps(distribution, coverage)
        assert len(gaps) == 1
        assert gaps[0]["coverage_count"] == 0

    def test_exact_threshold_excluded(self):
        """Weight exactly at 0.03 should be excluded (<=)."""
        distribution = {"borderline": 0.03}
        coverage = {"borderline": 0}
        gaps = _compute_gaps(distribution, coverage)
        assert gaps == []

    def test_coverage_exactly_three_not_a_gap(self):
        """Coverage of exactly 3 is not a gap (< 3 is the threshold)."""
        distribution = {"ai": 0.5}
        coverage = {"ai": 3}
        gaps = _compute_gaps(distribution, coverage)
        assert gaps == []
