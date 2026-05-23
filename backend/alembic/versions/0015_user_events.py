"""Phase 4 — Personal Memory Layer: user event tracking

Adds user_events table to track user interactions for interest profiling.

Revision ID: 0015
Revises: 0014
Create Date: 2026-05-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=True),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_user_events_user_time",
        "user_events",
        ["user_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_user_events_user_type_time",
        "user_events",
        ["user_id", "event_type", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_user_events_user_type_time", table_name="user_events")
    op.drop_index("idx_user_events_user_time", table_name="user_events")
    op.drop_table("user_events")
