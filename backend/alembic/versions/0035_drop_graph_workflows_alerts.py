"""drop graph_exports, workflows, alerts, feeds, notifications, push_subscriptions

The graph view, workflows, alerts, RSS feeds, notifications, push subscriptions,
and email settings features were removed from the codebase. This migration
drops the orphaned tables so the schema matches the live models.

Note: the entity / entity_edge / chunk_entity tables (created in 0002) are
kept — they're still used by Q&A retrieval, intelligence, and credibility.
Only the graph EXPORT (UI-specific snapshot) is being dropped here.

Revision ID: 0035
Revises: 0034
Create Date: 2026-05-24
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "0035"
down_revision: Union[str, None] = "0034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Order matters: drop children before parents.
# notifications -> alert_rules (FK), workflow_runs -> workflows (FK),
# rss_seen_items -> rss_feeds (FK).
_TABLES_IN_DROP_ORDER = (
    "notifications",
    "push_subscriptions",
    "alert_rules",
    "workflow_runs",
    "workflows",
    "email_settings",
    "rss_seen_items",
    "rss_feeds",
    "graph_exports",
)


def upgrade() -> None:
    for table in _TABLES_IN_DROP_ORDER:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")


def downgrade() -> None:
    raise NotImplementedError(
        "0035 is a one-way drop. The corresponding application code "
        "(routes, models, services, workers) has been deleted, so there "
        "is nothing left to query these tables. Restore from backup if "
        "you need the data."
    )
