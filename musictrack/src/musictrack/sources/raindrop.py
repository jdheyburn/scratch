"""Turning Raindrop bookmarks into reconcile candidates.

Named `to_listen`, not `wants`, to match `sources/spotify.py`'s adapter for
the same kind of list — a bookmark says "listen to this," not "buy this."
`reconcile`'s own report groups it under its "wants" bucket later, same as
Spotify's; that's the report's vocabulary, not this source's.
"""

from __future__ import annotations

from musictrack.models import AlbumRef
from musictrack.plan import is_music
from musictrack.raindrop_identity import parse_release


def to_listen(client) -> list[AlbumRef]:
    """Every Raindrop bookmark that names a release.

    Skips anything that isn't a music link, and anything whose title
    doesn't parse into (artist, album) — including every Bandcamp Daily
    article, which `parse_release` already refuses by domain. A miss here
    costs nothing, the same rule the dedupe fuzzy-matcher already lives by.
    """
    refs = []
    for bookmark in client.all_raindrops():
        if not is_music(bookmark):
            continue
        parsed = parse_release(bookmark)
        if parsed is None:
            continue
        artist, album = parsed
        refs.append(
            AlbumRef(
                source="raindrop",
                artist=artist,
                album=album,
                ref=str(bookmark.id),
                url=bookmark.link,
            )
        )
    return refs
