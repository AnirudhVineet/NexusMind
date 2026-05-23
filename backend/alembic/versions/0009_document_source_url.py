"""Phase 3.3 – add source_url to documents

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-17
"""

from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("source_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "source_url")
