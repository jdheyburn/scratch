"""Which library record a candidate is, if any.

Matches are trustworthy and absences are not. Across 338 collection matches an
exact key with an agreeing artist was right essentially every time, while `not
found` was wrong nine times in ten: shops and taggers name the same record
differently and every difference reads as absence. So the verdicts are graded,
and the caller is expected to present `ABSENT` as a candidate to check rather
than as work to do.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from musictrack.albumkey import agree, artists, key, loose
from musictrack.models import AlbumRef

OWNED = "owned"
POSSIBLE = "possible"
ABSENT = "absent"


@dataclass(frozen=True)
class Match:
    """A verdict, and what produced it."""

    verdict: str
    library: AlbumRef | None = None
    tier: str = ""


def variants(artist: str, album: str) -> list[tuple[str, str]]:
    """The artist/title readings worth trying, most trusted first.

    Bandcamp's `band_name` is often the label rather than the artist, with the
    real artist sitting in the title: `Kontakt Records` selling `Blue Channel -
    Dubplate Vibing Part I`. Sometimes it merely repeats itself, as in `Paul
    St. Hilaire - Paul St. Hilaire - Tikiman Vol.1`. Reading the title both
    ways took the unmatched count from 17 to 10.
    """
    readings = [(artist, album)]
    if " - " in album:
        head, tail = album.split(" - ", 1)
        readings.append((head, tail))
        readings.append((artist, tail))
    return readings


class LibraryIndex:
    """The library, keyed four ways: albums and tracks, at both tiers."""

    def __init__(self, albums: Sequence[AlbumRef], tracks: Sequence[AlbumRef]) -> None:
        self._album_exact: dict[str, list[AlbumRef]] = defaultdict(list)
        self._album_loose: dict[str, list[AlbumRef]] = defaultdict(list)
        self._track_exact: dict[str, list[AlbumRef]] = defaultdict(list)
        self._track_loose: dict[str, list[AlbumRef]] = defaultdict(list)
        for ref in albums:
            self._album_exact[key(ref.album)].append(ref)
            self._album_loose[loose(ref.album)].append(ref)
        for ref in tracks:
            self._track_exact[key(ref.album)].append(ref)
            self._track_loose[loose(ref.album)].append(ref)

    def look_up(self, candidate: AlbumRef) -> Match:
        """Albums before tracks, exact before loose, for each reading in turn."""
        tiers = (
            (self._album_exact, key, OWNED, "album-exact"),
            (self._album_loose, loose, POSSIBLE, "album-loose"),
            (self._track_exact, key, OWNED, "track-exact"),
            (self._track_loose, loose, POSSIBLE, "track-loose"),
        )
        for artist_text, album_text in variants(candidate.artist, candidate.album):
            wanted = artists(artist_text)
            for index, make_key, verdict, tier in tiers:
                for found in index.get(make_key(album_text), ()):
                    if agree(wanted, artists(found.artist)):
                        return Match(verdict, found, tier)
        # The title is in the library but under a different artist. Worth
        # showing: it is how a mis-credited release surfaces.
        for index, make_key in ((self._album_exact, key), (self._album_loose, loose)):
            hits = index.get(make_key(candidate.album))
            if hits:
                return Match(POSSIBLE, hits[0], "title-only")
        return Match(ABSENT)
