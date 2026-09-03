"""What beets holds, as two dumps.

Both dumps are needed. A single-track purchase imports as a singleton with an
empty album field, so `beet ls -a` cannot see it: of 27 Bandcamp track
purchases, 21 are in the library and none of them appears in the album dump.
Reporting those as missing would be the tool's most common lie.

Two dumps rather than a query per candidate. Asking beets about each of the
1897 candidates one at a time would be 1897 SSH round trips for the same
answer.
"""

from __future__ import annotations

from collections.abc import Callable

from musiclib.remote import run_remote

from musictrack.errors import LibraryError
from musictrack.models import AlbumRef

Runner = Callable[[str], str]

# Not `|`. The library holds `Two Hands | One Engine` as an album artist and
# `Bok Bok x Modjo - Raining x 'Lady'` as a track, and a pipe delimiter splits
# those rows in the wrong place without ever raising anything.
DELIMITER = "@@"

ALBUM_FORMAT = f"$albumartist{DELIMITER}$album"
TRACK_FORMAT = f"$artist{DELIMITER}$title{DELIMITER}$album{DELIMITER}$albumartist"


def _lines(run: Runner, script: str) -> list[str]:
    try:
        output = run(script)
    except Exception as problem:
        raise LibraryError(f"could not read the beets library: {problem}") from problem
    return [line for line in output.splitlines() if line.strip()]


def album_refs(run: Runner = run_remote) -> list[AlbumRef]:
    """Every album beets holds."""
    found = []
    for line in _lines(run, f"beet ls -a -f '{ALBUM_FORMAT}'"):
        parts = line.split(DELIMITER)
        if len(parts) != 2:
            continue
        found.append(AlbumRef(source="beets", artist=parts[0], album=parts[1], ref=""))
    return found


def track_refs(run: Runner = run_remote) -> list[AlbumRef]:
    """Every track beets holds, carried as its own release.

    `album` holds the track title, because for a singleton that is the only
    name the record has.
    """
    found = []
    for line in _lines(run, f"beet ls -f '{TRACK_FORMAT}'"):
        parts = line.split(DELIMITER)
        if len(parts) != 4:
            continue
        found.append(AlbumRef(source="beets-track", artist=parts[0], album=parts[1], ref=""))
    return found
