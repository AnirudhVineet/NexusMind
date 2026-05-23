"""Phase 4 Track C – Timeline View: create chunk_topics table.

Stores BERTopic cluster assignments per chunk, used by the timeline and
conflict-map views to filter and group content by topic cluster.

Revision ID: 0019
Revises: 0018
Create Date: 2026-05-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chunk_topics",
        sa.Column(
            "chunk_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("cluster_id", sa.Integer(), nullable=False),
        sa.Column("cluster_label", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["chunks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("chunk_id"),
    )
    op.create_index("idx_chunk_topics_cluster", "chunk_topics", ["cluster_id"])


def downgrade() -> None:
    op.drop_index("idx_chunk_topics_cluster", table_name="chunk_topics")
    op.drop_table("chunk_topics")
