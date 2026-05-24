"""Tests for event logging middleware — Phase 4 Track A.

Covers: _match_event_type, _extract_user_id, ALLOWED_EVENT_TYPES,
and the EventCreate validation at the API level.
"""
import uuid

import pytest

from app.middleware.event_logger import PATH_TO_EVENT, _extract_user_id, _match_event_type
from app.models.user_event import ALLOWED_EVENT_TYPES


# ---------------------------------------------------------------------------
# _match_event_type
# ---------------------------------------------------------------------------

class TestMatchEventType:
    """Verify that the path-to-event mapping is correct."""

    def test_exact_qa_match(self):
        assert _match_event_type("/qa") == "query"

    def test_qa_stream_match(self):
        assert _match_event_type("/qa/stream") == "query"

    def test_search_match(self):
        assert _match_event_type("/api/search") == "search_performed"

    def test_cards_prefix_match(self):
        uid = uuid.uuid4()
        assert _match_event_type(f"/api/cards/{uid}/review") == "card_reviewed"

    def test_annotations_match(self):
        assert _match_event_type("/api/annotations") == "annotation_created"

    def test_unknown_path_returns_none(self):
        assert _match_event_type("/api/documents") is None

    def test_empty_path_returns_none(self):
        assert _match_event_type("") is None


# ---------------------------------------------------------------------------
# _extract_user_id
# ---------------------------------------------------------------------------

class TestExtractUserId:
    """Verify JWT user_id extraction (without signature verification)."""

    def test_none_authorization_returns_none(self):
        assert _extract_user_id(None) is None

    def test_empty_string_returns_none(self):
        assert _extract_user_id("") is None

    def test_malformed_header_returns_none(self):
        assert _extract_user_id("Basic abc123") is None

    def test_invalid_token_returns_none(self):
        assert _extract_user_id("Bearer not-a-jwt") is None

    def test_valid_jwt_extracts_user_id(self):
        import jwt as pyjwt

        user_id = uuid.uuid4()
        token = pyjwt.encode({"sub": str(user_id)}, "secret", algorithm="HS256")
        result = _extract_user_id(f"Bearer {token}")
        assert result == user_id

    def test_jwt_without_sub_returns_none(self):
        import jwt as pyjwt

        token = pyjwt.encode({"role": "admin"}, "secret", algorithm="HS256")
        assert _extract_user_id(f"Bearer {token}") is None


# ---------------------------------------------------------------------------
# ALLOWED_EVENT_TYPES
# ---------------------------------------------------------------------------

class TestAllowedEventTypes:
    """Verify the allowed event type list is complete."""

    EXPECTED = {
        "query",
        "qa_answer_viewed",
        "document_viewed",
        "chunk_saved",
        "citation_clicked",
        "search_performed",
        "annotation_created",
        "card_reviewed",
    }

    def test_all_expected_types_present(self):
        assert set(ALLOWED_EVENT_TYPES) == self.EXPECTED

    def test_no_duplicates(self):
        assert len(ALLOWED_EVENT_TYPES) == len(set(ALLOWED_EVENT_TYPES))


# ---------------------------------------------------------------------------
# PATH_TO_EVENT consistency
# ---------------------------------------------------------------------------

class TestPathToEventConsistency:
    """All event types used in the middleware must be in the allowed set."""

    def test_middleware_event_types_are_allowed(self):
        for path, event_type in PATH_TO_EVENT.items():
            assert event_type in ALLOWED_EVENT_TYPES, (
                f"PATH_TO_EVENT[{path!r}] = {event_type!r} is not in ALLOWED_EVENT_TYPES"
            )
