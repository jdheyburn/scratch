"""Where a run's rows come from.

Two vocabularies meet here. Rows are stored under the `AlbumRef.source` value
that produced them, five of those. The user names sources the way they go
stale, three of those: both beets dumps come from one SSH session, both
Bandcamp lists from one authenticated client.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from musictrack.cache import SourceCache

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
