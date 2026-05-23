"""Phase 2.5 – source credibility scoring

Adds credibility_score + breakdown to documents and creates the
source_type_signals lookup table with seed data.

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # Credibility columns on documents                                    #
    # ------------------------------------------------------------------ #
    op.add_column("documents", sa.Column("credibility_score", sa.Float(), nullable=True))
    op.add_column(
        "documents",
        sa.Column(
            "credibility_breakdown",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "documents",
        sa.Column("credibility_computed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_docs_credibility",
        "documents",
        ["user_id", sa.text("credibility_score DESC NULLS LAST")],
    )

    # ------------------------------------------------------------------ #
    # Source type signals lookup table                                    #
    # ------------------------------------------------------------------ #
    op.create_table(
        "source_type_signals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("match_kind", sa.String(length=16), nullable=False),
        sa.Column("match_value", sa.String(length=256), nullable=False),
        sa.Column("source_label", sa.String(length=32), nullable=False),
        sa.Column("signal_value", sa.Float(), nullable=False),
        sa.Column("half_life_days", sa.Integer(), nullable=False),
        sa.Column(
            "priority", sa.Integer(), nullable=False, server_default=sa.text("100")
        ),
        sa.CheckConstraint(
            "match_kind IN ('mime', 'host_regex', 'path_regex')",
            name="ck_sts_match_kind",
        ),
        sa.CheckConstraint(
            "signal_value BETWEEN 0 AND 1", name="ck_sts_signal_value"
        ),
        sa.UniqueConstraint("match_kind", "match_value", name="uq_sts_match"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Seed default signal rows. Lower priority integer = higher priority (wins).
    op.execute(
        """
        INSERT INTO source_type_signals
            (match_kind, match_value, source_label, signal_value, half_life_days, priority)
        VALUES
            ('host_regex', '^(arxiv|nature|acm|ieee|springer|nih)\\.', 'peer_reviewed', 0.90, 730, 10),
            ('host_regex', '\\.(gov|edu)$',                            'official_docs', 0.85, 365, 20),
            ('host_regex', '^(nytimes|wsj|bbc|reuters|apnews)\\.',     'news',          0.65,  30, 30),
            ('host_regex', '^(medium|substack|dev\\.to|hashnode)',      'blog',          0.40,  90, 40),
            ('host_regex', '^(reddit|stackoverflow|hn\\.algolia)',      'forum',         0.30,  30, 40),
            ('mime',       'application/pdf',                           'document',      0.75, 730, 50),
            ('mime',       'text/plain',                                'text',          0.50, 180, 60),
            ('mime',       'text/markdown',                             'text',          0.50, 180, 60),
            ('host_regex', '.*',                                        'unknown',       0.50, 180, 999)
        """
    )


def downgrade() -> None:
    op.drop_table("source_type_signals")
    op.drop_index("idx_docs_credibility", table_name="documents")
    op.drop_column("documents", "credibility_computed_at")
    op.drop_column("documents", "credibility_breakdown")
    op.drop_column("documents", "credibility_score")
