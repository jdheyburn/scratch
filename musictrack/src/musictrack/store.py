"""The one thing about this tool that cannot be re-derived: your judgement.

Some correct matches should stay. Owning the digital and wanting the vinyl is a
real position, and so is an absence that turns out to be a naming difference.
Without somewhere to record those, every run reports them again until the
report gets skimmed and stops working.

This module holds decisions. `cache.py` holds copies of the sources, in the
same database. That split was once a rule that no source copy be stored at all,
on the grounds that a local mirror lets the tool answer from stale data while
looking healthy. The objection was right about the danger and wrong about the
remedy: what makes a cache dangerous is being invisible, so the cache carries a
fetch time and every report prints its age.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

DB_PATH = Path.home() / ".local" / "share" / "musictrack" / "musictrack.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS dismissal (
  source  TEXT NOT NULL,
  ref     TEXT NOT NULL,
  reason  TEXT,
  created TEXT NOT NULL,
  PRIMARY KEY (source, ref)
)
"""


class Dismissals:
    """Rows the reports should stop showing."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or DB_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._path) as db:
            db.execute(SCHEMA)

    def add(self, source: str, ref: str, reason: str = "") -> None:
        """Record one decision. Dismissing again replaces the reason."""
        with sqlite3.connect(self._path) as db:
            db.execute(
                "INSERT INTO dismissal (source, ref, reason, created) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(source, ref) DO UPDATE SET reason=excluded.reason, "
                "created=excluded.created",
                (source, ref, reason, datetime.now(UTC).isoformat()),
            )

    def hidden(self) -> dict[tuple[str, str], str]:
        """Every dismissal, keyed the way a report row is identified."""
        with sqlite3.connect(self._path) as db:
            rows = db.execute("SELECT source, ref, reason FROM dismissal").fetchall()
        return {(source, ref): reason or "" for source, ref, reason in rows}
