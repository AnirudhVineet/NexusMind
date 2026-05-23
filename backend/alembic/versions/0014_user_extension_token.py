"""Phase 3.4 — Browser Extension

Adds extension_token_issued_at to users so old extension tokens can be
invalidated when the user rotates their token.

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "extension_token_issued_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "extension_token_issued_at")
