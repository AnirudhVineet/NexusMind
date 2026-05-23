"""Tests for keyword-match alerts — Phase 4 Track G.

Covers: keyword matching logic (substring + case-insensitive).
"""
import pytest


def _check_keywords(keywords: list[str], searchable: str) -> list[str]:
    """Simulate the keyword match logic from alerts.py."""
    searchable_lower = searchable.lower()
    return [kw for kw in keywords if kw.lower() in searchable_lower]


class TestKeywordMatch:
    """Test keyword matching in document content."""

    def test_exact_match(self):
        matched = _check_keywords(["machine learning"], "This is about machine learning")
        assert matched == ["machine learning"]

    def test_case_insensitive(self):
        matched = _check_keywords(["AI"], "Advances in ai and deep learning")
        assert matched == ["AI"]

    def test_no_match(self):
        matched = _check_keywords(["quantum"], "This is about biology")
        assert matched == []

    def test_multiple_keywords_matched(self):
        matched = _check_keywords(
            ["neural", "deep", "quantum"],
            "Neural networks and deep learning",
        )
        assert set(matched) == {"neural", "deep"}

    def test_substring_match(self):
        matched = _check_keywords(["learn"], "This is about machine learning")
        assert matched == ["learn"]

    def test_empty_keywords(self):
        matched = _check_keywords([], "Any content here")
        assert matched == []

    def test_empty_content(self):
        matched = _check_keywords(["ai"], "")
        assert matched == []

    def test_keyword_in_title_and_body(self):
        searchable = "AI Ethics " + "The ethics of artificial intelligence"
        matched = _check_keywords(["ethics"], searchable)
        assert matched == ["ethics"]

    def test_special_characters_in_keyword(self):
        matched = _check_keywords(["C++"], "Programming in C++ is common")
        assert matched == ["C++"]
