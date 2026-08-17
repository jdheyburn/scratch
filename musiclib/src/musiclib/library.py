"""Asking beets what it actually holds.

Every destructive step goes through here first. Skipping an album at the beets
prompt must never look like a successful import.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path

from musiclib.albumfile import load_album, release_from_doc
from musiclib.remote import run_remote


@dataclass(frozen=True)
class LibraryAlbum:
    """An album beets holds, as reported by a query."""

    albumid: str
    artist: str
    album: str
    items: int


def gate_verdict(albums: int, files: list[str], expected: int | None) -> str | None:
    """None when an album is safely in the library; otherwise why it isn't."""
    if albums == 0:
        return "not in the library"
    if not expected:
        return "no transfer recorded for this album"
    if len(files) != expected:
        return f"library has {len(files)} items, expected {expected}"
    if "MISS" in files:
        return f"{files.count('MISS')} library file(s) missing on disk"
    return None


def choose_library_match(
    candidates: list[LibraryAlbum], expected: int | None
) -> LibraryAlbum | None:
    """The one album that is unambiguously ours, or nothing.

    You can pick a different pressing at the beets prompt than the one you
    captured — a legitimate call — so the applied id won't always equal the
    captured id. Fall back to the track count, but only when it identifies a
    single album: archiving is the next step, so ambiguity must not resolve.
    """
    if not expected:
        return None
    matches = [c for c in candidates if c.items == expected]
    return matches[0] if len(matches) == 1 else None


def library_search(artist: str, album: str, remote=None) -> list[LibraryAlbum]:
    """Find albums by name, for when the captured id isn't what beets applied."""
    remote = remote or run_remote
    out = remote(
        "beet ls -a "
        f"albumartist:{shlex.quote(artist)} album:{shlex.quote(album)} "
        "-f '$mb_albumid|$albumartist|$album|$albumtotal'"
    )
    found = []
    for line in filter(None, out.splitlines()):
        parts = line.split("|")
        if len(parts) == 4 and parts[3].strip().isdigit():
            found.append(LibraryAlbum(parts[0], parts[1], parts[2], int(parts[3])))
    return found


def library_report(discogs_id: int, remote=None) -> tuple[int, list[str]]:
    """Ask beets on dee what it holds for this release, and whether the files exist."""
    remote = remote or run_remote
    out = remote(
        f"beet ls -a mb_albumid:{discogs_id} -f '$album' | wc -l;"
        f"beet ls mb_albumid:{discogs_id} -f '$path' |"
        f' while IFS= read -r p; do [ -f "$p" ] && echo OK || echo MISS; done'
    ).split()
    return int(out[0] or 0), out[1:]


def album_count(discogs_id: str, remote=None) -> int:
    """How many albums beets holds under this release id."""
    remote = remote or run_remote
    return int(remote(f"beet ls -a mb_albumid:{discogs_id} -f '$album' | wc -l") or 0)


def applied_album(doc_path: Path, expected: int | None) -> LibraryAlbum | None:
    """Look the album up by name when the captured id isn't what beets applied."""
    release = release_from_doc(load_album(doc_path)) if doc_path.is_file() else None
    if release is None:
        return None
    return choose_library_match(library_search(release.artist, release.album), expected)
