"""Tests for graph serialization — Phase 4 Track E.

Covers: JSON, CSV, GraphML, GEXF output formats with a known test graph.
"""
import csv
import io
import json
import os
import tempfile
import zipfile

import networkx as nx
import pytest

from app.services.graph_export import serialize_graph


def _sample_graph() -> nx.MultiDiGraph:
    """Build a small deterministic graph for testing."""
    G = nx.MultiDiGraph()
    G.add_node("n1", name="Alice", canonical_name="alice", type="PERSON", evidence_count=3)
    G.add_node("n2", name="Bob", canonical_name="bob", type="PERSON", evidence_count=5)
    G.add_node("n3", name="OpenAI", canonical_name="openai", type="ORG", evidence_count=10)
    G.add_edge("n1", "n3", relation_type="WORKS_AT", confidence=0.95)
    G.add_edge("n2", "n3", relation_type="WORKS_AT", confidence=0.88)
    G.add_edge("n1", "n2", relation_type="KNOWS", confidence=0.7)
    return G


class TestJsonSerialization:
    """Test JSON (node_link_data) format."""

    def test_json_output_is_valid(self, tmp_path):
        path = str(tmp_path / "graph.json")
        size = serialize_graph(_sample_graph(), "json", path)
        assert size > 0

        data = json.loads(open(path, encoding="utf-8").read())
        assert "nodes" in data
        assert "edges" in data or "links" in data

    def test_json_node_count(self, tmp_path):
        path = str(tmp_path / "graph.json")
        serialize_graph(_sample_graph(), "json", path)
        data = json.loads(open(path, encoding="utf-8").read())
        assert len(data["nodes"]) == 3

    def test_json_edge_count(self, tmp_path):
        path = str(tmp_path / "graph.json")
        serialize_graph(_sample_graph(), "json", path)
        data = json.loads(open(path, encoding="utf-8").read())
        edges_key = "edges" if "edges" in data else "links"
        assert len(data[edges_key]) == 3


class TestCsvSerialization:
    """Test CSV (zipped nodes + edges) format."""

    def test_csv_zip_created(self, tmp_path):
        path = str(tmp_path / "graph.zip")
        size = serialize_graph(_sample_graph(), "csv", path)
        assert size > 0
        assert zipfile.is_zipfile(path)

    def test_csv_zip_contains_both_files(self, tmp_path):
        path = str(tmp_path / "graph.zip")
        serialize_graph(_sample_graph(), "csv", path)
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            assert "nodes.csv" in names
            assert "edges.csv" in names

    def test_csv_node_columns(self, tmp_path):
        path = str(tmp_path / "graph.zip")
        serialize_graph(_sample_graph(), "csv", path)
        with zipfile.ZipFile(path) as zf:
            reader = csv.reader(io.StringIO(zf.read("nodes.csv").decode()))
            header = next(reader)
            assert "id" in header
            assert "name" in header
            assert "type" in header

    def test_csv_edge_columns(self, tmp_path):
        path = str(tmp_path / "graph.zip")
        serialize_graph(_sample_graph(), "csv", path)
        with zipfile.ZipFile(path) as zf:
            reader = csv.reader(io.StringIO(zf.read("edges.csv").decode()))
            header = next(reader)
            assert "source" in header
            assert "target" in header
            assert "relation_type" in header

    def test_csv_node_count(self, tmp_path):
        path = str(tmp_path / "graph.zip")
        serialize_graph(_sample_graph(), "csv", path)
        with zipfile.ZipFile(path) as zf:
            reader = csv.reader(io.StringIO(zf.read("nodes.csv").decode()))
            rows = list(reader)
            assert len(rows) == 4  # header + 3 nodes


class TestGraphmlSerialization:
    """Test GraphML format."""

    def test_graphml_created(self, tmp_path):
        path = str(tmp_path / "graph.graphml")
        size = serialize_graph(_sample_graph(), "graphml", path)
        assert size > 0
        content = open(path, encoding="utf-8").read()
        assert "graphml" in content.lower()


class TestGexfSerialization:
    """Test GEXF format."""

    def test_gexf_created(self, tmp_path):
        path = str(tmp_path / "graph.gexf")
        size = serialize_graph(_sample_graph(), "gexf", path)
        assert size > 0
        content = open(path, encoding="utf-8").read()
        assert "gexf" in content.lower()


class TestUnsupportedFormat:
    """Verify unsupported formats raise ValueError."""

    def test_invalid_format_raises(self, tmp_path):
        path = str(tmp_path / "graph.xyz")
        with pytest.raises(ValueError, match="Unsupported"):
            serialize_graph(_sample_graph(), "xyz", path)


class TestEmptyGraph:
    """Verify empty graph handling."""

    def test_json_empty_graph(self, tmp_path):
        G = nx.MultiDiGraph()
        path = str(tmp_path / "empty.json")
        size = serialize_graph(G, "json", path)
        assert size > 0
        data = json.loads(open(path, encoding="utf-8").read())
        assert len(data["nodes"]) == 0
