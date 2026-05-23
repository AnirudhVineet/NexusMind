"""Phase 3.3 – add ingestion_metadata JSONB to documents

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-17
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("ingestion_metadata", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("documents", "ingestion_metadata")
