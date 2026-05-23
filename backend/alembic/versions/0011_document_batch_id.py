"""Phase 3.3 – add ingestion_batch_id for ZIP bundle grouping

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-17
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "ingestion_batch_id",
            UUID(as_uuid=True),
            nullable=True,
            index=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("documents", "ingestion_batch_id")
