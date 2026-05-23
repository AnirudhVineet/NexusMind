"""drop search/conflicts/memory/timeline tables and columns

Removes the database surface for the Conflicts, Memory and Timeline features:

  * claim_contradictions          (Conflicts)
  * claims                        (Conflicts)
  * user_contradiction_state      (Conflicts — Phase 4 per-user resolution)
  * user_interest_profile         (Memory)
  * documents.event_date          (Timeline)
  * chunks.event_date             (Timeline)

(Search had no dedicated tables — only an API endpoint + Redis cache —
so nothing to drop here.)

Revision ID: 0033
Revises: 0032
Create Date: 2026-05-23
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "0033"
down_revision: Union[str, None] = "0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # All drops use IF EXISTS so this migration is safe to run regardless of
    # which prior migrations actually applied on this database — e.g. if a
    # fresh DB never ran 0018 (Timeline) or if a stale environment still has
    # rows we'd rather purge than preserve. Postgres-only syntax.

    # ── Drop Timeline indexes + columns ─────────────────────────────────────
    op.execute("DROP INDEX IF EXISTS ix_chunks_event_date")
    op.execute("DROP INDEX IF EXISTS ix_documents_event_date")
    op.execute("ALTER TABLE chunks    DROP COLUMN IF EXISTS event_date")
    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS event_date")

    # ── Drop Memory tables ──────────────────────────────────────────────────
    op.execute("DROP TABLE IF EXISTS user_interest_profile CASCADE")

    # ── Drop Conflicts tables (FK order: child first) ───────────────────────
    op.execute("DROP TABLE IF EXISTS user_contradiction_state CASCADE")
    op.execute("DROP TABLE IF EXISTS claim_contradictions CASCADE")
    op.execute("DROP TABLE IF EXISTS claims CASCADE")


def downgrade() -> None:
    # The features are removed from the codebase. A faithful downgrade would
    # have to re-create every table, index, FK, and the `event_date` columns
    # — but with no code or models left to populate them. Leave downgrade as
    # a no-op; restore from backup if you genuinely need this data back.
    raise NotImplementedError(
        "0033 is a one-way drop. Restore from a backup taken before this "
        "migration ran if you need these tables back."
    )
