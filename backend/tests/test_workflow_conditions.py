"""Tests for workflow condition evaluation — Phase 4 Track F.

Covers: _check_conditions pure function — topic_in, confidence_gte, source_type_in.
"""
import pytest

from app.services.workflows import _check_conditions


class TestTopicInCondition:
    """Test the topic_in condition."""

    def test_matching_topic(self):
        conditions = {"topic_in": ["ai", "ml"]}
        payload = {"topic": "ai"}
        assert _check_conditions(conditions, payload) is True

    def test_non_matching_topic(self):
        conditions = {"topic_in": ["ai", "ml"]}
        payload = {"topic": "history"}
        assert _check_conditions(conditions, payload) is False

    def test_match_via_tags(self):
        conditions = {"topic_in": ["ai"]}
        payload = {"tags": ["ai", "deep-learning"]}
        assert _check_conditions(conditions, payload) is True

    def test_no_topic_no_tags_fails(self):
        conditions = {"topic_in": ["ai"]}
        payload = {}
        assert _check_conditions(conditions, payload) is False

    def test_topic_in_as_single_value(self):
        conditions = {"topic_in": "ai"}
        payload = {"topic": "ai"}
        assert _check_conditions(conditions, payload) is True


class TestConfidenceGteCondition:
    """Test the confidence_gte condition."""

    def test_above_threshold(self):
        conditions = {"confidence_gte": 0.8}
        payload = {"confidence": 0.9}
        assert _check_conditions(conditions, payload) is True

    def test_below_threshold(self):
        conditions = {"confidence_gte": 0.8}
        payload = {"confidence": 0.5}
        assert _check_conditions(conditions, payload) is False

    def test_exact_threshold(self):
        conditions = {"confidence_gte": 0.8}
        payload = {"confidence": 0.8}
        assert _check_conditions(conditions, payload) is True

    def test_missing_confidence_defaults_to_one(self):
        conditions = {"confidence_gte": 0.5}
        payload = {}
        assert _check_conditions(conditions, payload) is True


class TestSourceTypeInCondition:
    """Test the source_type_in condition."""

    def test_matching_source(self):
        conditions = {"source_type_in": ["upload", "url"]}
        payload = {"source_type": "upload"}
        assert _check_conditions(conditions, payload) is True

    def test_non_matching_source(self):
        conditions = {"source_type_in": ["upload"]}
        payload = {"source_type": "youtube"}
        assert _check_conditions(conditions, payload) is False

    def test_missing_source_type_fails(self):
        conditions = {"source_type_in": ["upload"]}
        payload = {}
        assert _check_conditions(conditions, payload) is False


class TestCombinedConditions:
    """Test multiple conditions at once."""

    def test_all_pass(self):
        conditions = {
            "topic_in": ["ai"],
            "confidence_gte": 0.7,
            "source_type_in": ["upload"],
        }
        payload = {"topic": "ai", "confidence": 0.9, "source_type": "upload"}
        assert _check_conditions(conditions, payload) is True

    def test_one_fails(self):
        conditions = {
            "topic_in": ["ai"],
            "confidence_gte": 0.9,
        }
        payload = {"topic": "ai", "confidence": 0.5}
        assert _check_conditions(conditions, payload) is False


class TestEmptyConditions:
    """Empty conditions always pass."""

    def test_empty_conditions(self):
        assert _check_conditions({}, {}) is True

    def test_empty_conditions_any_payload(self):
        assert _check_conditions({}, {"topic": "ai", "confidence": 0.1}) is True


class TestUnknownConditions:
    """Unknown condition keys are silently ignored."""

    def test_unknown_key_ignored(self):
        conditions = {"future_feature": True}
        payload = {}
        assert _check_conditions(conditions, payload) is True
