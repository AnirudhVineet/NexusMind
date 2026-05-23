"""drop users.extension_token_issued_at

Removes the column that tracked the browser extension's currently-valid
token rotation timestamp. The Connections feature (which included the
browser extension, its API endpoints, and the JWT helpers around it) has
been removed from the codebase, so the column is dead weight.

Revision ID: 0034
Revises: 0033
Create Date: 2026-05-23
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "0034"
down_revision: Union[str, None] = "0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # IF EXISTS keeps this idempotent — running on a DB where 0014 was never
    # applied (fresh install bypassing the extension feature) is a no-op.
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS extension_token_issued_at")


def downgrade() -> None:
    raise NotImplementedError(
        "0034 is a one-way drop. Restore from backup if you need the column "
        "back; the application code that read/wrote it is also gone."
    )
