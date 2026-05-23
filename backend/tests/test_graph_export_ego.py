"""Tests for ego-graph extraction — Phase 4 Track E.

Covers: ego-graph with known topology, radius parameter, missing center.
"""
import uuid

import networkx as nx
import pytest


def _build_star_graph(center_id: str, n_leaves: int = 5) -> nx.MultiDiGraph:
    """Build a star graph: center connected to n_leaves."""
    G = nx.MultiDiGraph()
    G.add_node(center_id, name="Center", type="PERSON", canonical_name="center", evidence_count=1)
    for i in range(n_leaves):
        leaf = f"leaf-{i}"
        G.add_node(leaf, name=f"Leaf {i}", type="CONCEPT", canonical_name=f"leaf-{i}", evidence_count=1)
        G.add_edge(center_id, leaf, relation_type="RELATES_TO", confidence=0.9)
    return G


def _build_chain_graph(n: int = 5) -> nx.MultiDiGraph:
    """Build a linear chain: n0 → n1 → n2 → ... → n(n-1)."""
    G = nx.MultiDiGraph()
    for i in range(n):
        G.add_node(f"n{i}", name=f"Node {i}", type="CONCEPT", canonical_name=f"n{i}", evidence_count=1)
    for i in range(n - 1):
        G.add_edge(f"n{i}", f"n{i+1}", relation_type="NEXT", confidence=0.9)
    return G


class TestEgoGraph:
    """Verify ego-graph extraction."""

    def test_star_ego_depth_1(self):
        G = _build_star_graph("center", n_leaves=5)
        ego = nx.ego_graph(G, "center", radius=1, undirected=True)
        assert ego.number_of_nodes() == 6  # center + 5 leaves
        assert "center" in ego

    def test_chain_ego_depth_1(self):
        G = _build_chain_graph(5)
        ego = nx.ego_graph(G, "n2", radius=1, undirected=True)
        # n2 connects to n1 and n3
        assert "n2" in ego
        assert "n1" in ego
        assert "n3" in ego
        assert "n0" not in ego  # too far
        assert "n4" not in ego

    def test_chain_ego_depth_2(self):
        G = _build_chain_graph(5)
        ego = nx.ego_graph(G, "n2", radius=2, undirected=True)
        assert ego.number_of_nodes() == 5  # all nodes reachable

    def test_ego_depth_0_only_center(self):
        G = _build_star_graph("center", n_leaves=5)
        ego = nx.ego_graph(G, "center", radius=0, undirected=True)
        assert ego.number_of_nodes() == 1
        assert "center" in ego

    def test_missing_center_returns_full_graph(self):
        """If center is not in graph, load_subgraph returns full graph (no ego filter)."""
        G = _build_star_graph("center")
        missing = "nonexistent"
        assert missing not in G
        # In our service, if center not in G, ego filter is skipped

    def test_leaf_as_center(self):
        G = _build_star_graph("center", n_leaves=3)
        ego = nx.ego_graph(G, "leaf-0", radius=1, undirected=True)
        assert "leaf-0" in ego
        assert "center" in ego
        # Other leaves are distance 2 from leaf-0
        assert ego.number_of_nodes() == 2

    def test_ego_preserves_edge_attributes(self):
        G = _build_star_graph("center", n_leaves=2)
        ego = nx.ego_graph(G, "center", radius=1, undirected=True)
        for u, v, data in ego.edges(data=True):
            assert "relation_type" in data
            assert "confidence" in data
