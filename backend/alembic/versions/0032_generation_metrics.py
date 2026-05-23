"""Phase 5 Track H — Generation metrics + cleanup hooks

Adds an append-only generation_metrics table for per-job cost / latency /
provider attribution.

Revision ID: 0032
Revises: 0031
Create Date: 2026-05-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0032"
down_revision: Union[str, None] = "0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "generation_metrics",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("media_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("job_type", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("input_units", sa.Integer(), nullable=True),
        sa.Column("output_units", sa.Integer(), nullable=True),
        sa.Column(
            "cost_estimate_usd",
            sa.Numeric(10, 6),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error_class", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["media_job_id"], ["media_jobs.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "idx_gen_metrics_user_created",
        "generation_metrics",
        ["user_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_gen_metrics_job_type",
        "generation_metrics",
        ["job_type", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_gen_metrics_job_type", table_name="generation_metrics")
    op.drop_index("idx_gen_metrics_user_created", table_name="generation_metrics")
    op.drop_table("generation_metrics")
