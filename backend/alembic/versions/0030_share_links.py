"""Phase 5 Track F — Share links

Public share URLs for content / media / briefs with optional password +
expiry + view counter.

Revision ID: 0030
Revises: 0028
Create Date: 2026-05-22

Note: 0029 was intentionally left as a gap for a potential future
meme_assets migration. See docs/phase5/migrations.md.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0030"
down_revision: Union[str, None] = "0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "share_links",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_share_links_slug"),
    )
    op.create_index(
        "idx_share_links_user_created",
        "share_links",
        ["user_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_share_links_target", "share_links", ["target_type", "target_id"]
    )


def downgrade() -> None:
    op.drop_index("idx_share_links_target", table_name="share_links")
    op.drop_index("idx_share_links_user_created", table_name="share_links")
    op.drop_table("share_links")
