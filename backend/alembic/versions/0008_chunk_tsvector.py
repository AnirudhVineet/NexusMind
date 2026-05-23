"""Phase 3.1 – BM25: add tsvector column + GIN index + trigger to chunks

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add tsv column (nullable initially so backfill can populate it)
    op.add_column(
        "chunks",
        sa.Column("tsv", sa.Text(), nullable=True),
    )

    # Convert the column type to tsvector using server-side cast
    op.execute("ALTER TABLE chunks ALTER COLUMN tsv TYPE tsvector USING tsv::tsvector")

    # Create GIN index for fast full-text search
    op.execute("CREATE INDEX chunks_tsv_gin ON chunks USING GIN(tsv)")

    # Create trigger function + trigger to keep tsv in sync on insert/update
    op.execute("""
        CREATE OR REPLACE FUNCTION chunks_tsv_update_fn() RETURNS trigger AS $$
        BEGIN
            NEW.tsv := to_tsvector('pg_catalog.english', coalesce(NEW.text, ''));
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql
    """)

    op.execute("""
        CREATE TRIGGER chunks_tsv_update
        BEFORE INSERT OR UPDATE ON chunks
        FOR EACH ROW EXECUTE FUNCTION chunks_tsv_update_fn()
    """)

    # Backfill existing rows
    op.execute(
        "UPDATE chunks SET tsv = to_tsvector('pg_catalog.english', coalesce(text, ''))"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS chunks_tsv_update ON chunks")
    op.execute("DROP FUNCTION IF EXISTS chunks_tsv_update_fn()")
    op.execute("DROP INDEX IF EXISTS chunks_tsv_gin")
    op.drop_column("chunks", "tsv")
