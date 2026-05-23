"""Backfill event_date on documents and chunks.

Run: cd backend && python -m scripts.backfill_event_dates

Strategy (tried in order for each document without an event_date):
1. Parse from ingestion_metadata["captured_at"] if present.
2. Parse a date-like pattern from the first 1000 chars of the document's chunks.
3. Parse a date slug from source_url using r'\\d{4}[-/]\\d{1,2}[-/]\\d{1,2}'.

Once a date is found, it is written to the document and all its chunks.
Uses a synchronous psycopg2 session via DATABASE_SYNC_URL.
"""
from __future__ import annotations

import re
import sys
from datetime import date
from typing import Optional

import dateparser
from sqlalchemy import create_engine, text

from app.core.config import get_settings

DATE_SLUG_RE = re.compile(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}")


def _parse_date(value: str) -> Optional[date]:
    """Return a date from a string, or None if unparseable."""
    try:
        parsed = dateparser.parse(value, settings={"RETURN_AS_TIMEZONE_AWARE": False})
        if parsed is not None:
            return parsed.date()
    except Exception:
        pass
    return None


def _try_slug(url: Optional[str]) -> Optional[date]:
    if not url:
        return None
    m = DATE_SLUG_RE.search(url)
    if m:
        return _parse_date(m.group(0))
    return None


def main() -> None:
    settings = get_settings()
    engine = create_engine(settings.database_sync_url, echo=False, future=True)

    with engine.connect() as conn:
        # Fetch documents that have no event_date yet
        rows = conn.execute(
            text(
                """
                SELECT id, source_url, ingestion_metadata
                FROM documents
                WHERE event_date IS NULL
                ORDER BY id
                """
            )
        ).fetchall()

        total = len(rows)
        print(f"Found {total} documents without event_date.")

        updated = 0
        for idx, row in enumerate(rows, start=1):
            doc_id = row[0]
            source_url: Optional[str] = row[1]
            ingestion_metadata: Optional[dict] = row[2]

            resolved: Optional[date] = None

            # 1. ingestion_metadata["captured_at"]
            if resolved is None and ingestion_metadata:
                captured_at = ingestion_metadata.get("captured_at")
                if captured_at:
                    resolved = _parse_date(str(captured_at))

            # 2. First 1000 chars of chunk text content
            if resolved is None:
                chunk_rows = conn.execute(
                    text(
                        """
                        SELECT text
                        FROM chunks
                        WHERE document_id = :doc_id
                        ORDER BY chunk_index
                        LIMIT 5
                        """
                    ),
                    {"doc_id": str(doc_id)},
                ).fetchall()
                combined = " ".join(
                    (r[0] or "")[:200] for r in chunk_rows
                )[:1000]
                if combined:
                    m = DATE_SLUG_RE.search(combined)
                    if m:
                        resolved = _parse_date(m.group(0))

            # 3. URL slug
            if resolved is None:
                resolved = _try_slug(source_url)

            if resolved is None:
                if idx % 100 == 0:
                    print(f"  [{idx}/{total}] {doc_id}: no date found, skipping.")
                continue

            # Update document
            conn.execute(
                text(
                    "UPDATE documents SET event_date = :dt WHERE id = :doc_id"
                ),
                {"dt": resolved, "doc_id": str(doc_id)},
            )
            # Update all chunks for this document
            conn.execute(
                text(
                    "UPDATE chunks SET event_date = :dt WHERE document_id = :doc_id"
                ),
                {"dt": resolved, "doc_id": str(doc_id)},
            )
            updated += 1
            if idx % 50 == 0 or idx == total:
                print(f"  [{idx}/{total}] {doc_id}: set event_date={resolved}")

        conn.commit()

    print(f"Done. Updated {updated}/{total} documents.")


if __name__ == "__main__":
    main()
    sys.exit(0)
