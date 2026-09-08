"""Where a run's rows come from.

Two vocabularies meet here. Rows are stored under the `AlbumRef.source` value
that produced them, five of those. The user names sources the way they go
stale, three of those: both beets dumps come from one SSH session, both
Bandcamp lists from one authenticated client.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime

from rich.text import Text

from musictrack.cache import SourceCache, describe_age, is_stale
from musictrack.config import load_bandcamp_cookie
from musictrack.models import AlbumRef
from musictrack.sources import library as beets
from musictrack.sources.bandcamp import BandcampClient
from musictrack.sources.spotify import spotify_client, to_listen

ALL = "all"

BEETS = ("beets", "beets-track")
BANDCAMP = ("bandcamp-wishlist", "bandcamp-collection")
SPOTIFY = ("spotify",)

# Ordered, because this is also the order the age header prints in.
REFRESH_NAMES: dict[str, tuple[str, ...]] = {
    "beets": BEETS,
    "bandcamp": BANDCAMP,
    "spotify": SPOTIFY,
}

WANTS_KEYS = (*BEETS, "bandcamp-wishlist", "spotify")
BACKLOG_KEYS = (*BEETS, "bandcamp-collection")


class UnknownSource(Exception):
    """`--refresh` was given a name that is not a source."""


def keys_for(show_wants: bool, show_backlog: bool) -> tuple[str, ...]:
    """The storage keys the requested reports need, each once.

    A backlog-only run must not include `spotify`: reading it means
    authenticating to it.
    """
    wanted: list[str] = []
    if show_wants:
        wanted.extend(WANTS_KEYS)
    if show_backlog:
        wanted.extend(BACKLOG_KEYS)
    return tuple(dict.fromkeys(wanted))


def keys_to_refresh(name: str | None) -> frozenset[str]:
    """The storage keys a `--refresh` value covers."""
    if name is None:
        return frozenset()
    if name == ALL:
        return frozenset(key for keys in REFRESH_NAMES.values() for key in keys)
    if name not in REFRESH_NAMES:
        valid = ", ".join([ALL, *REFRESH_NAMES])
        raise UnknownSource(f"{name!r} is not a source. Use one of: {valid}")
    return frozenset(REFRESH_NAMES[name])


def source_ages(cache: SourceCache, keys: Sequence[str]) -> list[tuple[str, datetime | None]]:
    """When each named source was last read, for the keys this run used.

    A name covering two keys reports the older of them, so a header can never
    flatter a pair that has drifted apart.
    """
    ages: list[tuple[str, datetime | None]] = []
    for name, members in REFRESH_NAMES.items():
        used = [key for key in members if key in keys]
        if not used:
            continue
        stamps = [cache.fetched_at(key) for key in used]
        known = [stamp for stamp in stamps if stamp is not None]
        ages.append((name, min(known) if len(known) == len(stamps) and known else None))
    return ages


Fetcher = Callable[[], list[AlbumRef]]


class Fetchers:
    """One live read per storage key, each built only when it is called.

    Laziness is the point. A fully cached run calls none of these, and so needs
    no Bandcamp cookie and no Spotify token. A backlog run calls neither of the
    Spotify or wishlist readers, so it authenticates to neither.
    """

    def __init__(self) -> None:
        self._bandcamp: BandcampClient | None = None

    def _client(self) -> BandcampClient:
        if self._bandcamp is None:
            self._bandcamp = BandcampClient(load_bandcamp_cookie())
        return self._bandcamp

    def as_map(self) -> dict[str, Fetcher]:
        return {
            "beets": beets.album_refs,
            "beets-track": beets.track_refs,
            "bandcamp-wishlist": lambda: self._client().wishlist(),
            "bandcamp-collection": lambda: self._client().collection(),
            "spotify": lambda: to_listen(spotify_client()),
        }


@dataclass
class Gathered:
    """The rows this run will work from, and which of them were read live."""

    rows: dict[str, list[AlbumRef]] = field(default_factory=dict)
    fetched: set[str] = field(default_factory=set)


def gather(
    cache: SourceCache,
    fetchers: Mapping[str, Fetcher],
    keys: Sequence[str],
    refresh: str | None = None,
) -> Gathered:
    """Rows for every key, from the cache where there is one.

    The refresh name is resolved first, so an unrecognised one costs a message
    rather than a source read.
    """
    refreshing = keys_to_refresh(refresh)
    result = Gathered()
    for key in keys:
        if key in refreshing or not cache.has(key):
            refs = fetchers[key]()
            cache.write(key, refs)
            result.rows[key] = refs
            result.fetched.add(key)
        else:
            result.rows[key] = cache.read(key)
    return result


def age_line(ages: Sequence[tuple[str, datetime | None]], now: datetime) -> Text:
    """One line naming every source the run used and how old its copy is.

    This is what makes the cache safe to have. A stale copy cannot look healthy
    while its age is on the report it feeds.
    """
    line = Text()
    stale = False
    for position, (name, when) in enumerate(ages):
        if position:
            line.append(" · ", style="dim")
        old = is_stale(when, now)
        stale = stale or old
        line.append(f"{name} {describe_age(when, now)}", style="yellow" if old else "dim")
    if stale:
        line.append("   --refresh all to update", style="yellow")
    return line
