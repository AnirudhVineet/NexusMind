"""Phase 4 Track F — Scheduled RSS Ingestion: rss_feeds, rss_seen_items tables.

Revision ID: 0023
Revises: 0022
Create Date: 2026-05-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── rss_feeds ──────────────────────────────────────────────────────────────
    op.create_table(
        "rss_feeds",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column(
            "title",
            sa.Text(),
            server_default=sa.text("''"),
            nullable=False,
        ),
        sa.Column(
            "interval_minutes",
            sa.Integer(),
            server_default=sa.text("360"),
            nullable=False,
        ),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_etag", sa.Text(), nullable=True),
        sa.Column("last_modified", sa.Text(), nullable=True),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_rss_feeds_user",
        "rss_feeds",
        ["user_id", "enabled"],
        postgresql_using="btree",
    )

    # ── rss_seen_items ─────────────────────────────────────────────────────────
    op.create_table(
        "rss_seen_items",
        sa.Column("feed_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_guid", sa.Text(), nullable=False),
        sa.Column(
            "seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["feed_id"], ["rss_feeds.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("feed_id", "item_guid"),
    )


def downgrade() -> None:
    op.drop_table("rss_seen_items")
    op.drop_index("idx_rss_feeds_user", table_name="rss_feeds")
    op.drop_table("rss_feeds")
