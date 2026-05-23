"""Phase 4 Track C – Timeline View: add event_date columns to documents and chunks.

Revision ID: 0018
Revises: 0017
Create Date: 2026-05-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("event_date", sa.Date(), nullable=True))
    op.add_column("chunks", sa.Column("event_date", sa.Date(), nullable=True))
    op.create_index("idx_documents_event_date", "documents", ["event_date"])
    op.create_index("idx_chunks_event_date", "chunks", ["event_date"])


def downgrade() -> None:
    op.drop_index("idx_chunks_event_date", table_name="chunks")
    op.drop_index("idx_documents_event_date", table_name="documents")
    op.drop_column("chunks", "event_date")
    op.drop_column("documents", "event_date")
