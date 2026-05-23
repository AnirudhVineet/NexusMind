"""Phase 5 Track B — User voice preferences + brief narrations

Adds user_voice_preferences (default voice + speed per user) and
brief_narrations (chapter manifest per research brief).

Revision ID: 0028
Revises: 0027
Create Date: 2026-05-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0028"
down_revision: Union[str, None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_voice_preferences",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("default_voice_id", sa.Text(), nullable=True),
        sa.Column(
            "speed", sa.Numeric(3, 2), nullable=False, server_default=sa.text("1.0")
        ),
        sa.Column(
            "last_used_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "brief_narrations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brief_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("media_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "chapters",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("voice_id", sa.Text(), nullable=True),
        sa.Column("speed", sa.Numeric(3, 2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["brief_id"], ["research_briefs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["media_job_id"], ["media_jobs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_brief_narrations_brief", "brief_narrations", ["brief_id"]
    )


def downgrade() -> None:
    op.drop_index("idx_brief_narrations_brief", table_name="brief_narrations")
    op.drop_table("brief_narrations")
    op.drop_table("user_voice_preferences")
