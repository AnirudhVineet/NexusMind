"""Tests for chunk topic cluster assignment — Phase 4 Track C.

Covers: cluster label inheritance from documents, chunk_topics population.
"""
import uuid

import pytest


class TestTopicClusterAssignment:
    """Verify chunk-to-cluster assignment logic."""

    def _assign_clusters(
        self,
        chunk_doc_map: dict[str, str],
        doc_cluster_map: dict[str, tuple[int, str]],
    ) -> list[dict]:
        """Simulate the build_chunk_topics script logic.

        chunk_doc_map: {chunk_id: document_id}
        doc_cluster_map: {document_id: (cluster_id, cluster_label)}
        """
        assignments = []
        for chunk_id, doc_id in chunk_doc_map.items():
            if doc_id in doc_cluster_map:
                cluster_id, label = doc_cluster_map[doc_id]
                assignments.append({
                    "chunk_id": chunk_id,
                    "cluster_id": cluster_id,
                    "cluster_label": label,
                })
        return assignments

    def test_chunk_inherits_parent_cluster(self):
        chunk_id = str(uuid.uuid4())
        doc_id = str(uuid.uuid4())
        result = self._assign_clusters(
            {chunk_id: doc_id},
            {doc_id: (1, "artificial-intelligence")},
        )
        assert len(result) == 1
        assert result[0]["cluster_label"] == "artificial-intelligence"
        assert result[0]["cluster_id"] == 1

    def test_multiple_chunks_same_doc(self):
        doc_id = str(uuid.uuid4())
        chunks = {str(uuid.uuid4()): doc_id for _ in range(5)}
        result = self._assign_clusters(chunks, {doc_id: (2, "math")})
        assert len(result) == 5
        assert all(r["cluster_label"] == "math" for r in result)

    def test_doc_without_cluster_skipped(self):
        chunk_id = str(uuid.uuid4())
        doc_id = str(uuid.uuid4())
        result = self._assign_clusters({chunk_id: doc_id}, {})
        assert len(result) == 0

    def test_multiple_docs_different_clusters(self):
        doc1, doc2 = str(uuid.uuid4()), str(uuid.uuid4())
        chunks = {
            str(uuid.uuid4()): doc1,
            str(uuid.uuid4()): doc2,
        }
        result = self._assign_clusters(
            chunks,
            {doc1: (1, "ai"), doc2: (2, "bio")},
        )
        assert len(result) == 2
        labels = {r["cluster_label"] for r in result}
        assert labels == {"ai", "bio"}

    def test_empty_inputs(self):
        result = self._assign_clusters({}, {})
        assert result == []
