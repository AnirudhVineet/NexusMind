"""task_runs idempotency table

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-12 00:00:02

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "task_runs",
        sa.Column("scope_type", sa.String(length=16), nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_name", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "scope_type IN ('chunk','document')", name="ck_task_runs_scope_type"
        ),
        sa.CheckConstraint(
            "status IN ('started','success','failed')", name="ck_task_runs_status"
        ),
        sa.PrimaryKeyConstraint(
            "scope_type", "scope_id", "task_name", name="pk_task_runs"
        ),
    )


def downgrade() -> None:
    op.drop_table("task_runs")
