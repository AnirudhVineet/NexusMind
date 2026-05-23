"""document intelligence + topic tags

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-12 00:00:01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("intelligence", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("intelligence_computed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "topic_tags",
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
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("bertopic_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source IN ('bertopic','llm','manual')", name="ck_topic_tags_source"
        ),
        sa.UniqueConstraint("user_id", "slug", name="uq_topic_tags_user_slug"),
    )

    op.create_table(
        "document_tags",
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tag_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("topic_tags.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("document_id", "tag_id", name="pk_document_tags"),
    )
    op.create_index("idx_doctag_tag", "document_tags", ["tag_id"])


def downgrade() -> None:
    op.drop_index("idx_doctag_tag", table_name="document_tags")
    op.drop_table("document_tags")
    op.drop_table("topic_tags")
    op.drop_column("documents", "intelligence_computed_at")
    op.drop_column("documents", "intelligence")
