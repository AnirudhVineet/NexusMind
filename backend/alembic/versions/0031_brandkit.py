"""Phase 5 Track G — Brand Kit

One row per user holding colors, fonts, logo/watermark asset refs, music
default, and subtitle style JSON.

Revision ID: 0031
Revises: 0030
Create Date: 2026-05-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0031"
down_revision: Union[str, None] = "0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "brand_kits",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("primary_color", sa.Text(), nullable=True),
        sa.Column("secondary_color", sa.Text(), nullable=True),
        sa.Column("accent_color", sa.Text(), nullable=True),
        sa.Column("font_heading", sa.Text(), nullable=True),
        sa.Column("font_body", sa.Text(), nullable=True),
        sa.Column("logo_asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("watermark_asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "watermark_opacity",
            sa.Numeric(3, 2),
            nullable=False,
            server_default=sa.text("0.6"),
        ),
        sa.Column(
            "watermark_position",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'bottom-right'"),
        ),
        sa.Column("music_style_default", sa.Text(), nullable=True),
        sa.Column(
            "subtitle_style",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["logo_asset_id"], ["media_assets.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["watermark_asset_id"], ["media_assets.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("brand_kits")
