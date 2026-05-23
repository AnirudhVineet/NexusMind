"""Phase 2.5 – claim contradictions table

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "claim_contradictions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_a_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_b_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("embedding_similarity", sa.Float(), nullable=False),
        sa.Column("nli_contradiction_score", sa.Float(), nullable=False),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default="auto"
        ),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "embedding_similarity BETWEEN 0 AND 1", name="ck_cc_emb_sim"
        ),
        sa.CheckConstraint(
            "nli_contradiction_score BETWEEN 0 AND 1", name="ck_cc_nli_score"
        ),
        sa.CheckConstraint(
            "status IN ('auto', 'confirmed', 'dismissed')", name="ck_cc_status"
        ),
        # Canonical ordering prevents (A,B) and (B,A) duplicates.
        sa.CheckConstraint("claim_a_id < claim_b_id", name="ck_cc_canonical_order"),
        sa.UniqueConstraint("claim_a_id", "claim_b_id", name="uq_claim_contradictions_pair"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["claim_a_id"], ["claims.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["claim_b_id"], ["claims.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "idx_cc_user_status", "claim_contradictions", ["user_id", "status"]
    )
    op.create_index("idx_cc_claim_a", "claim_contradictions", ["claim_a_id"])
    op.create_index("idx_cc_claim_b", "claim_contradictions", ["claim_b_id"])


def downgrade() -> None:
    op.drop_index("idx_cc_claim_b", table_name="claim_contradictions")
    op.drop_index("idx_cc_claim_a", table_name="claim_contradictions")
    op.drop_index("idx_cc_user_status", table_name="claim_contradictions")
    op.drop_table("claim_contradictions")
