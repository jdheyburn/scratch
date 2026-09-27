"""Which Plex album a library match is, so it can be opened and checked.

Keyed the way the matcher keys beets, with exact keys only: Plex and beets read
the same tags, so a loose key would add guesses and no real hits. Measured on
2026-09-27, 1926 of 2020 beets albums agree with a Plex album on artist and
title, and all but 2 share a title with one.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence

from rich.markup import escape

from musictrack.albumkey import agree, artists, key
from musictrack.cache import SourceCache
from musictrack.console import console
from musictrack.errors import PlexError
from musictrack.gather import PLEX, Fetcher, gather
from musictrack.models import AlbumRef


class PlexIndex:
    """Plex albums and tracks, each keyed by title."""

    def __init__(self, albums: Sequence[AlbumRef], tracks: Sequence[AlbumRef]) -> None:
        self._albums: dict[str, list[AlbumRef]] = defaultdict(list)
        self._tracks: dict[str, list[AlbumRef]] = defaultdict(list)
        for ref in albums:
            self._albums[key(ref.album)].append(ref)
        for ref in tracks:
            self._tracks[key(ref.album)].append(ref)

    @classmethod
    def empty(cls) -> PlexIndex:
        return cls([], [])

    def links(self, found: AlbumRef | None) -> list[str]:
        """The Plex album links for the beets record a match picked.

        A track hit links to the album the track is on. An artist spelled
        differently still links when only one row holds the title; with two or
        more, picking one would be a guess, so nothing links.
        """
        if found is None:
            return []
        title = key(found.album)
        if not title:
            return []
        index = self._tracks if found.source == "beets-track" else self._albums
        rows = index.get(title, [])
        wanted = artists(found.artist)
        hits = [row for row in rows if agree(wanted, artists(row.artist))]
        if not hits and len(rows) == 1:
            hits = rows
        return list(dict.fromkeys(row.url for row in hits))


def load_plex(
    cache: SourceCache, fetchers: Mapping[str, Fetcher], refresh: str | None
) -> PlexIndex:
    """This run's Plex links, or none.

    Gathered apart from the report's own sources: a link is a convenience,
    never report data, so a Plex failure warns and the run carries on. A key
    whose read failed is never cached, so a failure never reads back later as
    an empty Plex.
    """
    try:
        rows = gather(cache, fetchers, PLEX, refresh).rows
    except PlexError as problem:
        console.print(f"[yellow]no Plex links this run: {escape(str(problem))}[/]")
        return PlexIndex.empty()
    return PlexIndex(rows["plex-album"], rows["plex-track"])
