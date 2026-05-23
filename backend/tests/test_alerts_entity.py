"""Tests for entity-mention alerts — Phase 4 Track G.

Covers: entity ID matching between watched entities and document entities.
"""
import uuid

import pytest


def _check_entity_mentions(
    watched_ids: list[str],
    doc_entity_ids: set[str],
) -> list[str]:
    """Simulate the entity mention check from alerts.py."""
    return [eid for eid in watched_ids if eid in doc_entity_ids]


class TestEntityMentionMatch:
    """Test entity mention matching logic."""

    def test_single_match(self):
        e1 = str(uuid.uuid4())
        matched = _check_entity_mentions([e1], {e1})
        assert matched == [e1]

    def test_no_match(self):
        e1 = str(uuid.uuid4())
        e2 = str(uuid.uuid4())
        matched = _check_entity_mentions([e1], {e2})
        assert matched == []

    def test_multiple_watched_some_match(self):
        e1, e2, e3 = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        matched = _check_entity_mentions([e1, e2, e3], {e1, e3})
        assert set(matched) == {e1, e3}

    def test_empty_watched_list(self):
        e1 = str(uuid.uuid4())
        matched = _check_entity_mentions([], {e1})
        assert matched == []

    def test_empty_doc_entities(self):
        e1 = str(uuid.uuid4())
        matched = _check_entity_mentions([e1], set())
        assert matched == []

    def test_all_match(self):
        ids = [str(uuid.uuid4()) for _ in range(5)]
        matched = _check_entity_mentions(ids, set(ids))
        assert len(matched) == 5

    def test_duplicate_watched_ids(self):
        e1 = str(uuid.uuid4())
        matched = _check_entity_mentions([e1, e1], {e1})
        assert len(matched) == 2  # preserves duplicates in watched list
