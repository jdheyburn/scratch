"""A copy of what each source last said, so a report does not have to ask again.

Parsed rows, never raw payloads. `AlbumRef` is what the matcher consumes, so a
cached read and a live read hand the index the same thing, and the account
identifiers the payloads carry are never written to disk.

A source that returned nothing is not a source that was never read. That
difference lives in `cache_run`, and every "do we have this?" question is
answered from there rather than from a row count.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from musictrack.models import AlbumRef
from musictrack.store import DB_PATH

SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS cache_run (
      source  TEXT PRIMARY KEY,
      fetched TEXT NOT NULL,
      refs    INTEGER NOT NULL
    )
    """,
    # No primary key. Every beets row carries an empty `ref`, so (source, ref)
    # is not unique there, and two records can share an artist and a title.
    # These rows are a dump to replay, not a set to address.
    """
    CREATE TABLE IF NOT EXISTS cached_ref (
      source TEXT NOT NULL,
      artist TEXT NOT NULL,
      album  TEXT NOT NULL,
      ref    TEXT NOT NULL,
      url    TEXT NOT NULL DEFAULT ''
    )
    """,
    "CREATE INDEX IF NOT EXISTS cached_ref_source ON cached_ref (source)",
)


class SourceCache:
    """What each source last returned, keyed by `AlbumRef.source`."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or DB_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._path) as db:
            for statement in SCHEMA:
                db.execute(statement)

    def fetched_at(self, source: str) -> datetime | None:
        """When this source was last read, or nothing if it never has been."""
        with sqlite3.connect(self._path) as db:
            row = db.execute("SELECT fetched FROM cache_run WHERE source = ?", (source,)).fetchone()
        return datetime.fromisoformat(row[0]) if row else None

    def has(self, source: str) -> bool:
        """Whether this source has ever been read. Not whether it has rows."""
        return self.fetched_at(source) is not None

    def read(self, source: str) -> list[AlbumRef]:
        """Every row stored for this source, in the order it was written."""
        with sqlite3.connect(self._path) as db:
            rows = db.execute(
                "SELECT artist, album, ref, url FROM cached_ref WHERE source = ? ORDER BY rowid",
                (source,),
            ).fetchall()
        return [
            AlbumRef(source=source, artist=artist, album=album, ref=ref, url=url)
            for artist, album, ref, url in rows
        ]

    def write(self, source: str, refs: Sequence[AlbumRef]) -> None:
        """Replace this source's rows and record when it was read.

        One transaction. The caller only reaches here once the fetch has
        returned in full, so a read that failed part-way leaves the previous
        copy in place rather than replacing it with half of one.
        """
        now = datetime.now(UTC).isoformat()
        with sqlite3.connect(self._path) as db:
            db.execute("DELETE FROM cached_ref WHERE source = ?", (source,))
            db.executemany(
                "INSERT INTO cached_ref (source, artist, album, ref, url) VALUES (?, ?, ?, ?, ?)",
                [(source, r.artist, r.album, r.ref, r.url) for r in refs],
            )
            db.execute(
                "INSERT INTO cache_run (source, fetched, refs) VALUES (?, ?, ?) "
                "ON CONFLICT(source) DO UPDATE SET fetched=excluded.fetched, "
                "refs=excluded.refs",
                (source, now, len(refs)),
            )
