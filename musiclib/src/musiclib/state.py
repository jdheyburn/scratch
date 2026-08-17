"""Where the rips live, and the bookkeeping beside them.

Everything under `.state/` is re-derivable and safe to delete: the beets
library is always the authority on whether an album actually imported.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from musiclib import yamlio

VINYL_ROOT = Path.home() / "Music" / "vinyl"

DONE_DIRNAME = "done"
STATE_DIRNAME = ".state"
# Long enough to re-split a record if you're going to, short enough that a Mac
# with 29 GiB free doesn't fill up.
RETENTION_DAYS = 21


def timestamp() -> str:
    """What goes into the `*_at` fields: local time, to the second."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def find_albums(root: Path) -> list[Path]:
    """Album directories waiting to be dealt with — anything holding FLACs."""
    return sorted(
        (
            d
            for d in root.iterdir()
            if d.is_dir()
            and d.name not in {DONE_DIRNAME, STATE_DIRNAME}
            and not d.name.startswith(".")
            and any(d.glob("*.flac"))
        ),
        key=lambda d: d.name,
    )


def _state_path(root: Path, slug: str) -> Path:
    return root / STATE_DIRNAME / f"{slug}.yaml"


def read_state(root: Path, slug: str) -> dict:
    """Bookkeeping for one album. Everything in here is re-derivable."""
    path = _state_path(root, slug)
    if not path.is_file():
        return {}
    return dict(yamlio.load(path) or {})


def update_state(root: Path, slug: str, **fields) -> dict:
    state = read_state(root, slug) | fields
    path = _state_path(root, slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    yamlio.dump(path, state)
    return state


def all_states(root: Path) -> dict[str, dict]:
    """Every album we have bookkeeping for, keyed by slug."""
    state_dir = root / STATE_DIRNAME
    if not state_dir.is_dir():
        return {}
    return {p.stem: read_state(root, p.stem) for p in sorted(state_dir.glob("*.yaml"))}


def expired_albums(
    root: Path, now: datetime, days: int = RETENTION_DAYS
) -> list[tuple[str, timedelta]]:
    """Archived albums past the retention window, with how long they've sat there."""
    out = []
    for slug, state in all_states(root).items():
        stamp = state.get("archived_at")
        if not stamp:
            continue
        try:
            archived_at = datetime.fromisoformat(str(stamp))
        except ValueError:
            # Never delete on the strength of a date we couldn't read.
            continue
        age = now - archived_at
        if age > timedelta(days=days):
            out.append((slug, age))
    return out
