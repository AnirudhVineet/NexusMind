"""Phase 5 Track A — Media Jobs table

Adds media_jobs table for tracking async render pipelines (reels, narrations,
storyboards, meme images, exports).

Revision ID: 0026
Revises: 0025
Create Date: 2026-05-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0026"
down_revision: Union[str, None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "media_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("job_type", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'queued'"),
        ),
        sa.Column(
            "params",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "progress_pct",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("stage", sa.Text(), nullable=True),
        sa.Column("output_path", sa.Text(), nullable=True),
        sa.Column("output_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column(
            "duration_seconds",
            sa.Numeric(10, 3),
            nullable=True,
        ),
        sa.Column(
            "cost_estimate_usd",
            sa.Numeric(10, 6),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["content_id"], ["generated_content.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_media_jobs_user_created",
        "media_jobs",
        ["user_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_media_jobs_status_created",
        "media_jobs",
        ["status", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_media_jobs_content",
        "media_jobs",
        ["content_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_media_jobs_content", table_name="media_jobs")
    op.drop_index("idx_media_jobs_status_created", table_name="media_jobs")
    op.drop_index("idx_media_jobs_user_created", table_name="media_jobs")
    op.drop_table("media_jobs")
