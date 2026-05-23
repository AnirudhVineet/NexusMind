"""Tests for Reciprocal Rank Fusion — pure function, no I/O."""
import uuid

import pytest


def _ids(n: int) -> list[uuid.UUID]:
    return [uuid.uuid4() for _ in range(n)]


def test_rrf_single_list():
    from app.services.retrieval import rrf_merge

    ids = _ids(5)
    result = rrf_merge([ids])
    assert result == ids  # single list preserves order


def test_rrf_two_identical_lists():
    from app.services.retrieval import rrf_merge

    ids = _ids(4)
    result = rrf_merge([ids, ids])
    # Same order — each id scores double but relative order unchanged
    assert result == ids


def test_rrf_two_disjoint_lists():
    from app.services.retrieval import rrf_merge

    a = _ids(3)
    b = _ids(3)
    result = rrf_merge([a, b])
    # All 6 ids should appear
    assert set(result) == set(a) | set(b)
    # First item of each list scores 1/(k+1); a[0] and b[0] are tied
    assert result[0] in {a[0], b[0]}


def test_rrf_overlap_boosts_shared_ids():
    from app.services.retrieval import rrf_merge

    shared = uuid.uuid4()
    unique_a = uuid.uuid4()
    unique_b = uuid.uuid4()
    list_a = [shared, unique_a]
    list_b = [shared, unique_b]
    result = rrf_merge([list_a, list_b])
    # shared appears in both lists → highest score
    assert result[0] == shared


def test_rrf_empty_lists():
    from app.services.retrieval import rrf_merge

    result = rrf_merge([[], []])
    assert result == []


def test_rrf_one_empty_one_full():
    from app.services.retrieval import rrf_merge

    ids = _ids(3)
    result = rrf_merge([ids, []])
    assert result == ids


def test_rrf_k_parameter_affects_scores():
    from app.services.retrieval import rrf_merge

    a = [uuid.uuid4(), uuid.uuid4()]
    b = [uuid.uuid4(), a[0]]  # a[0] appears in both — should be first
    result_low_k = rrf_merge([a, b], k=1)
    result_high_k = rrf_merge([a, b], k=1000)
    # In both cases a[0] should be first since it appears in both lists
    assert result_low_k[0] == a[0]
    assert result_high_k[0] == a[0]
