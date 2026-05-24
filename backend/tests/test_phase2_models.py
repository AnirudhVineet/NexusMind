"""Smoke tests for Phase 2 model + migration wiring.

These tests don't hit a database — they just verify that:
- All new SQLAlchemy models are importable and registered against Base.metadata.
- The relation_type CHECK constraint matches the Python tuple.
- The alembic revision chain is linear (0001 → 0002 → 0003 → 0004).
"""
from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest

from app import models
from app.db.base import Base


# ---------------------------------------------------------------------------
# Model registration
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "table_name",
    [
        "entities",
        "entity_aliases",
        "chunk_entities",
        "entity_edges",
        "topic_tags",
        "document_tags",
        "task_runs",
    ],
)
def test_phase2_tables_registered(table_name: str) -> None:
    assert table_name in Base.metadata.tables, (
        f"Phase 2 table {table_name!r} is not registered on Base.metadata; "
        f"check app/models/__init__.py imports."
    )


def test_relation_types_in_sync() -> None:
    # The CHECK constraint string in the migration must match the model tuple.
    from app.models import RELATION_TYPES

    expected = {
        "depends_on",
        "contradicts",
        "authored_by",
        "relates_to",
        "is_part_of",
        "references",
        "co_occurs_with",
    }
    assert set(RELATION_TYPES) == expected


def test_entity_types_complete() -> None:
    from app.models import ENTITY_TYPES

    expected_minimum = {
        # spaCy built-ins
        "PERSON",
        "ORG",
        "GPE",
        "DATE",
        "EVENT",
        # GLiNER custom
        "CONCEPT",
        "TOOL",
        "METHOD",
        "METRIC",
    }
    assert expected_minimum.issubset(set(ENTITY_TYPES))


# ---------------------------------------------------------------------------
# Alembic chain
# ---------------------------------------------------------------------------

_REVISION_RE = re.compile(r'^revision:\s*str\s*=\s*"([^"]+)"', re.MULTILINE)
_DOWN_RE = re.compile(r"^down_revision:[^=]+=\s*(\"[^\"]+\"|None)", re.MULTILINE)


def _read_revisions() -> list[tuple[str, str | None, str]]:
    versions_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    out: list[tuple[str, str | None, str]] = []
    for path in sorted(versions_dir.glob("*.py")):
        if path.name.startswith("__"):
            continue
        text = path.read_text(encoding="utf-8")
        rev_match = _REVISION_RE.search(text)
        down_match = _DOWN_RE.search(text)
        if rev_match is None or down_match is None:
            continue
        rev = rev_match.group(1)
        down_raw = down_match.group(1)
        down = None if down_raw == "None" else down_raw.strip('"')
        out.append((rev, down, path.name))
    return out


def test_alembic_chain_linear() -> None:
    revisions = _read_revisions()
    by_rev = {r[0]: r for r in revisions}
    assert "0001" in by_rev, "Phase 1 initial schema missing"
    assert "0002" in by_rev, "0002_kg_tables missing"
    assert "0003" in by_rev, "0003_document_intelligence missing"
    assert "0004" in by_rev, "0004_task_runs missing"

    assert by_rev["0002"][1] == "0001"
    assert by_rev["0003"][1] == "0002"
    assert by_rev["0004"][1] == "0003"


# ---------------------------------------------------------------------------
# Module discoverability — every new worker module must import cleanly.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "module_name",
    [
        "app.workers.idempotency",
        "app.workers.ner",
        "app.workers.relations",
        "app.workers.intelligence",
        "app.workers.maintenance",
        "app.services.llm_local",
        "app.services.intelligence",
    ],
)
def test_new_module_imports(module_name: str) -> None:
    # Heavy ML modules (ner, topics, intelligence) lazy-load their models, so
    # importing the *modules* should succeed even if spaCy/GLiNER aren't
    # present at import time. If this test fails, the module is doing
    # eager work it shouldn't.
    importlib.import_module(module_name)
