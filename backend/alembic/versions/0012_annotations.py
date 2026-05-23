"""Phase 3.5 – Notes & annotation system

Adds the annotations table for user highlights and notes. A note with body
text is later projected into the knowledge graph as a `user_insight` entity.

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "annotations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("insight_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("highlight_text", sa.Text(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=True),
        sa.Column("char_end", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "color", sa.String(length=16), nullable=False, server_default="yellow"
        ),
        # Replaced with a real pgvector column immediately below.
        sa.Column("embedding", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "color IN ('yellow', 'green', 'blue', 'pink', 'purple')",
            name="ck_annotations_color",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chunk_id"], ["chunks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["insight_entity_id"], ["entities.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # all-MiniLM-L6-v2 produces 384-dim embeddings — same space as entities.
    op.execute("ALTER TABLE annotations DROP COLUMN embedding")
    op.execute("ALTER TABLE annotations ADD COLUMN embedding vector(384)")

    op.create_index(
        "idx_annotations_user_doc", "annotations", ["user_id", "document_id"]
    )
    op.create_index(
        "idx_annotations_user_chunk", "annotations", ["user_id", "chunk_id"]
    )
    op.create_index(
        "idx_annotations_tags_gin",
        "annotations",
        ["tags"],
        postgresql_using="gin",
    )
    op.create_index(
        "idx_annotations_user_created",
        "annotations",
        ["user_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_annotations_user_created", table_name="annotations")
    op.drop_index("idx_annotations_tags_gin", table_name="annotations")
    op.drop_index("idx_annotations_user_chunk", table_name="annotations")
    op.drop_index("idx_annotations_user_doc", table_name="annotations")
    op.drop_table("annotations")
