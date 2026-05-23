"""Phase 3.6 – Spaced repetition system

Adds flashcards and flashcard_reviews tables for SM-2 scheduled review.

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "flashcards",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("reps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("interval_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ease", sa.Float(), nullable=False, server_default="2.5"),
        sa.Column(
            "due_date",
            sa.Date(),
            nullable=False,
            server_default=sa.text("CURRENT_DATE"),
        ),
        sa.Column(
            "suspended", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("ease >= 1.3", name="ck_flashcards_ease"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chunk_id"], ["chunks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # Partial index — the due-cards query only ever wants un-suspended cards.
    op.create_index(
        "idx_cards_user_due",
        "flashcards",
        ["user_id", "due_date"],
        postgresql_where=sa.text("NOT suspended"),
    )
    op.create_index("idx_cards_document", "flashcards", ["user_id", "document_id"])

    op.create_table(
        "flashcard_reviews",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("card_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("rating BETWEEN 0 AND 3", name="ck_reviews_rating"),
        sa.ForeignKeyConstraint(
            ["card_id"], ["flashcards.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_reviews_card", "flashcard_reviews", ["card_id"])


def downgrade() -> None:
    op.drop_index("idx_reviews_card", table_name="flashcard_reviews")
    op.drop_table("flashcard_reviews")
    op.drop_index("idx_cards_document", table_name="flashcards")
    op.drop_index("idx_cards_user_due", table_name="flashcards")
    op.drop_table("flashcards")
