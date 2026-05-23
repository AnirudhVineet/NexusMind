"""knowledge graph tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-12 00:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ALLOWED_RELATION_TYPES = (
    "depends_on",
    "contradicts",
    "authored_by",
    "relates_to",
    "is_part_of",
    "references",
    "co_occurs_with",
)


def upgrade() -> None:
    op.create_table(
        "entities",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("canonical_name", sa.String(length=512), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("evidence_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("idx_entities_user_type", "entities", ["user_id", "type"])
    op.create_index(
        "idx_entities_canon",
        "entities",
        ["user_id", "type", "canonical_name"],
    )
    op.execute(
        "CREATE INDEX idx_entities_embedding_hnsw "
        "ON entities USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )

    op.create_table(
        "entity_aliases",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "entity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("surface_form", sa.String(length=512), nullable=False),
        sa.UniqueConstraint("entity_id", "surface_form", name="uq_entity_aliases_form"),
    )

    op.create_table(
        "chunk_entities",
        sa.Column(
            "chunk_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chunks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "entity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint(
            "chunk_id", "entity_id", "char_start", name="pk_chunk_entities"
        ),
    )
    op.create_index("idx_ce_entity", "chunk_entities", ["entity_id"])

    op.create_table(
        "entity_edges",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "src_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "dst_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relation_type", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column(
            "evidence_chunk_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chunks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "relation_type IN ("
            + ", ".join(f"'{r}'" for r in ALLOWED_RELATION_TYPES)
            + ")",
            name="ck_entity_edges_relation_type",
        ),
        sa.CheckConstraint(
            "confidence BETWEEN 0 AND 1", name="ck_entity_edges_confidence"
        ),
        sa.UniqueConstraint(
            "src_id",
            "dst_id",
            "relation_type",
            "evidence_chunk_id",
            name="uq_entity_edges_dedup",
        ),
    )
    op.create_index("idx_edges_src", "entity_edges", ["src_id", "relation_type"])
    op.create_index("idx_edges_dst", "entity_edges", ["dst_id", "relation_type"])
    op.execute(
        "CREATE INDEX idx_edges_user_conf "
        "ON entity_edges (user_id, confidence DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_edges_user_conf")
    op.drop_index("idx_edges_dst", table_name="entity_edges")
    op.drop_index("idx_edges_src", table_name="entity_edges")
    op.drop_table("entity_edges")
    op.drop_index("idx_ce_entity", table_name="chunk_entities")
    op.drop_table("chunk_entities")
    op.drop_table("entity_aliases")
    op.execute("DROP INDEX IF EXISTS idx_entities_embedding_hnsw")
    op.drop_index("idx_entities_canon", table_name="entities")
    op.drop_index("idx_entities_user_type", table_name="entities")
    op.drop_table("entities")
