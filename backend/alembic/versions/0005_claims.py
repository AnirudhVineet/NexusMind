"""Phase 2.5 – atomic claims layer

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "claims",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("polarity", sa.String(length=8), nullable=False),
        sa.Column("primary_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        # bge-base-en-v1.5 produces 768-dim embeddings
        sa.Column("embedding", sa.Text(), nullable=True),  # stored as pgvector via raw SQL
        sa.Column("llm_confidence", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("polarity IN ('affirm', 'negate')", name="ck_claims_polarity"),
        sa.CheckConstraint("llm_confidence BETWEEN 0 AND 1", name="ck_claims_llm_confidence"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chunk_id"], ["chunks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["primary_entity_id"], ["entities.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Add the real vector column via raw DDL after table creation so pgvector
    # extension handles the type registration correctly.
    op.execute("ALTER TABLE claims DROP COLUMN embedding")
    op.execute("ALTER TABLE claims ADD COLUMN embedding vector(768)")

    op.create_index("idx_claims_user_doc", "claims", ["user_id", "document_id"])
    op.create_index("idx_claims_chunk", "claims", ["chunk_id"])
    op.create_index(
        "idx_claims_primary_ent",
        "claims",
        ["primary_entity_id"],
        postgresql_where=sa.text("primary_entity_id IS NOT NULL"),
    )
    op.execute(
        "CREATE INDEX idx_claims_embedding ON claims "
        "USING hnsw (embedding vector_cosine_ops) "
        "WHERE embedding IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_claims_embedding")
    op.drop_index("idx_claims_primary_ent", table_name="claims")
    op.drop_index("idx_claims_chunk", table_name="claims")
    op.drop_index("idx_claims_user_doc", table_name="claims")
    op.drop_table("claims")
