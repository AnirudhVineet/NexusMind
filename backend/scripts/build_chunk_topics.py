"""Populate chunk_topics from document_tags → topic_tags hierarchy.

For each chunk, inherit the highest-confidence topic tag of its parent document.
The cluster_id is taken from topic_tags.bertopic_id (falling back to a
synthetic integer derived from the tag's rowid when bertopic_id is NULL).

Run: cd backend && python -m scripts.build_chunk_topics

Uses INSERT ... ON CONFLICT DO NOTHING for idempotency.
Uses a synchronous psycopg2 session via DATABASE_SYNC_URL.
"""
from __future__ import annotations

import sys

from sqlalchemy import create_engine, text

from app.core.config import get_settings


def main() -> None:
    settings = get_settings()
    engine = create_engine(settings.database_sync_url, echo=False, future=True)

    with engine.connect() as conn:
        # For each chunk, find the highest-confidence topic tag on its parent document.
        # Use DISTINCT ON (chunk_id) with ORDER BY confidence DESC to get the best match.
        result = conn.execute(
            text(
                """
                INSERT INTO chunk_topics (chunk_id, cluster_id, cluster_label)
                SELECT DISTINCT ON (c.id)
                    c.id                                                   AS chunk_id,
                    COALESCE(
                        tt.bertopic_id,
                        -- Synthetic fallback: use a stable integer from the UUID bytes
                        ABS(
                            ('x' || SUBSTR(tt.id::text, 1, 8))::bit(32)::int
                        )
                    )                                                      AS cluster_id,
                    tt.display_name                                        AS cluster_label
                FROM chunks c
                JOIN document_tags dt ON dt.document_id = c.document_id
                JOIN topic_tags tt    ON tt.id = dt.tag_id
                ORDER BY c.id, dt.confidence DESC
                ON CONFLICT (chunk_id) DO NOTHING
                """
            )
        )
        inserted = result.rowcount
        conn.commit()

    print(f"Done. Inserted {inserted} rows into chunk_topics.")


if __name__ == "__main__":
    main()
    sys.exit(0)
