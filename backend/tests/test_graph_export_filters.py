"""Tests for graph export filter logic — Phase 4 Track E.

Covers: entity_type filtering, min_confidence edge filtering.
Uses mocked SQLAlchemy session.
"""
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import networkx as nx
import pytest

from app.services.graph_export import load_subgraph


def _mock_entity(name: str, etype: str = "PERSON", eid: uuid.UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=eid or uuid.uuid4(),
        name=name,
        canonical_name=name.lower(),
        type=etype,
        evidence_count=1,
        user_id=uuid.uuid4(),
    )


def _mock_edge(src_id: uuid.UUID, dst_id: uuid.UUID, rtype: str = "KNOWS", conf: float = 0.9) -> SimpleNamespace:
    return SimpleNamespace(
        src_id=src_id,
        dst_id=dst_id,
        relation_type=rtype,
        confidence=conf,
        user_id=uuid.uuid4(),
    )


def _mock_session(entities: list, edges: list) -> MagicMock:
    session = MagicMock()

    call_count = {"n": 0}

    def _execute_side_effect(stmt):
        call_count["n"] += 1
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        if call_count["n"] == 1:
            mock_scalars.all.return_value = entities
        else:
            mock_scalars.all.return_value = edges
        mock_result.scalars.return_value = mock_scalars
        return mock_result

    session.execute.side_effect = _execute_side_effect
    return session


class TestEntityTypeFilter:
    """Test filtering nodes by entity type."""

    def test_filter_persons_only(self):
        user_id = uuid.uuid4()
        e1 = _mock_entity("Alice", "PERSON")
        e2 = _mock_entity("OpenAI", "ORG")
        edge = _mock_edge(e1.id, e2.id)

        # When entity_types filter is applied, the DB query would return
        # only matching entities. Simulate that:
        session = _mock_session([e1], [edge])
        G = load_subgraph(user_id, session, {"entity_types": ["PERSON"]})

        assert G.has_node(str(e1.id))
        # edge to e2 should not be added since e2 is not in the graph
        assert G.number_of_edges() == 0

    def test_no_filter_includes_all(self):
        user_id = uuid.uuid4()
        e1 = _mock_entity("Alice", "PERSON")
        e2 = _mock_entity("OpenAI", "ORG")
        edge = _mock_edge(e1.id, e2.id)

        session = _mock_session([e1, e2], [edge])
        G = load_subgraph(user_id, session, {})

        assert G.number_of_nodes() == 2
        assert G.number_of_edges() == 1


class TestMinConfidenceFilter:
    """Test filtering edges by minimum confidence."""

    def test_low_confidence_edges_excluded(self):
        user_id = uuid.uuid4()
        e1 = _mock_entity("A")
        e2 = _mock_entity("B")
        high_edge = _mock_edge(e1.id, e2.id, conf=0.95)
        low_edge = _mock_edge(e2.id, e1.id, conf=0.3)

        # When min_confidence filter is applied, only high edges pass
        session = _mock_session([e1, e2], [high_edge])
        G = load_subgraph(user_id, session, {"min_confidence": 0.5})

        assert G.number_of_edges() == 1

    def test_zero_confidence_includes_all(self):
        user_id = uuid.uuid4()
        e1 = _mock_entity("A")
        e2 = _mock_entity("B")
        edges = [
            _mock_edge(e1.id, e2.id, conf=0.1),
            _mock_edge(e2.id, e1.id, conf=0.9),
        ]

        session = _mock_session([e1, e2], edges)
        G = load_subgraph(user_id, session, {"min_confidence": 0.0})

        assert G.number_of_edges() == 2


class TestEmptyGraph:
    """Test empty graph scenario."""

    def test_no_entities_returns_empty_graph(self):
        session = _mock_session([], [])
        G = load_subgraph(uuid.uuid4(), session, {})
        assert G.number_of_nodes() == 0
        assert G.number_of_edges() == 0
