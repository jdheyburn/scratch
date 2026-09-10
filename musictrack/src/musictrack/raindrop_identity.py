"""What makes two raindrops from different shops the same release.

Raindrop bookmarks carry no structured artist or album, but Raindrop's own
backend fetches the page `<title>` when a bookmark is saved, and every shop
below writes that title in a fixed, site-specific shape. Parsing it is
therefore free: no extra request, no scraping. Every failure below — a
domain this module doesn't know, a known domain whose page isn't a single
release, a raindrop Raindrop never fetched a title for — returns `None`
rather than a guess. A missed grouping costs nothing; a wrong one deletes
the wrong bookmark.
"""

# ruff: noqa: RUF001, RUF002

from __future__ import annotations

import html
import re
import unicodedata
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from urllib.parse import urlparse

from musictrack.albumkey import CATALOGUE, CATALOGUE_COLON, FORMAT_TAIL, agree, artists, loose
from musictrack.models import Raindrop


def _domain_of(link: str) -> str:
    return urlparse(link).netloc.lower().removeprefix("www.")


def is_bandcamp(raindrop: Raindrop) -> bool:
    domain = _domain_of(raindrop.link)
    return domain == "bandcamp.com" or domain.endswith(".bandcamp.com")


def _bandcamp(title: str) -> tuple[str, str] | None:
    """`{Album} | {Artist}`, with an optional trailing `| {Label}`."""
    parts = [part.strip() for part in title.split("|")]
    if len(parts) < 2:
        return None
    return parts[1], parts[0]


def _boomkat(title: str) -> tuple[str, str] | None:
    """`{Artist} - {Album} - Boomkat`."""
    if not title.endswith(" - Boomkat"):
        return None
    body = title[: -len(" - Boomkat")]
    if " - " not in body:
        return None
    artist, album = body.split(" - ", 1)
    return artist.strip(), album.strip()


def _bleep(title: str) -> tuple[str, str] | None:
    """`{Artist} - {Title}. Bleep.`."""
    if not title.endswith(". Bleep."):
        return None
    body = title[: -len(". Bleep.")]
    if " - " not in body:
        return None
    artist, album = body.split(" - ", 1)
    return artist.strip(), album.strip()


def _phonica(title: str) -> tuple[str, str] | None:
    """`{ARTIST}/{Album}/{Label} - Vinyl Records...`."""
    parts = title.split("/")
    if len(parts) < 3:
        return None
    return parts[0].strip(), parts[1].strip()


def _rubadub(title: str) -> tuple[str, str] | None:
    """`[Pre-Order: ]{Artist} - {Album}[ (Label)][ – Rubadub]`.

    Less uniform than the other four — a few titles pack a second
    ` - `-separated segment in before the label. Splitting on the first
    ` - ` still returns a usable artist; a messy album half costs a missed
    grouping, never a wrong one.
    """
    body = title
    if body.startswith("Pre-Order: "):
        body = body[len("Pre-Order: ") :]
    if body.endswith(" – Rubadub"):
        body = body[: -len(" – Rubadub")]
    if " - " not in body:
        return None
    artist, album = body.split(" - ", 1)
    return artist.strip(), album.strip()


_PARSERS = {
    "boomkat.com": _boomkat,
    "bleep.com": _bleep,
    "phonicarecords.com": _phonica,
    "rubadub.co.uk": _rubadub,
}


def parse_release(raindrop: Raindrop) -> tuple[str, str] | None:
    """The (artist, album) a bookmark's title names, or `None`."""
    if not raindrop.title:
        return None
    title = html.unescape(raindrop.title)
    domain = _domain_of(raindrop.link)
    if domain == "daily.bandcamp.com":
        # An article page, not a release page. It happens to share the
        # `{Headline} | Bandcamp Daily` shape with `{Album} | {Artist}`, which
        # would parse every article as the same fake artist, "Bandcamp Daily".
        return None
    if is_bandcamp(raindrop):
        return _bandcamp(title)
    parser = _PARSERS.get(domain)
    if parser is None:
        return None
    return parser(title)


@dataclass(frozen=True)
class Cluster:
    """Two or more raindrops judged the same release, and why."""

    matched_as: tuple[str, str]
    raindrops: tuple[Raindrop, ...]


def _tail_kept(text: str) -> str:
    """What `loose()` does, minus its bracket and edition-tail stripping.

    `loose()` strips a catalogue-number prefix, an edition tail (`- Remaster`),
    a bracketed suffix, and a trailing format tag (`LP`, `EP`) — useful for
    matching against beets, but a bracket or edition tail is often the one
    thing distinguishing two different releases by the same artist
    (`White Line Sunrise III (Part 1)` vs `(Part 2)`; `Municipal Dreams` vs
    `Municipal Dreams (Remixes)`). This keeps that part in, so two album
    texts that agree here but disagree once fully loosened are disagreeing
    on something real, not on catalogue-prefix or format-tag noise.
    """
    folded = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    working = folded.lower()
    working = CATALOGUE.sub("", CATALOGUE_COLON.sub("", working))
    plain = re.sub(r"[^a-z0-9]+", " ", working).strip().removeprefix("the ")
    return FORMAT_TAIL.sub("", plain).strip()


def group_by_release(raindrops: Sequence[Raindrop]) -> list[Cluster]:
    """Cluster raindrops that look like the same release, across domains.

    Only raindrops whose title parses take part. Clustered by loose album
    key, then split further by artist agreement within a bucket — a bucket
    can in theory hold two different releases that coincidentally
    loose-match on title, and agreement is what keeps them apart
    (`albumkey.py`'s own docstring: loose matching "merges 39 albums that
    are different records" when used for beets matching).

    Artist agreement alone isn't enough, though: `loose()`'s bracket and
    edition-tail stripping can erase the one thing telling two same-artist
    releases apart. `_tail_kept` keeps that part in, so a candidate only
    joins a cluster if it agrees with the seed there too — a real difference
    in the stripped part refuses the pair, while a difference that's only
    catalogue-prefix or format-tag noise still clusters normally. A cluster
    of size one — nothing else agreed — is dropped.
    """
    parsed: dict[int, tuple[str, str]] = {}
    for raindrop in raindrops:
        result = parse_release(raindrop)
        if result:
            parsed[raindrop.id] = result

    buckets: dict[str, list[Raindrop]] = defaultdict(list)
    for raindrop in raindrops:
        if raindrop.id in parsed:
            album_key = loose(parsed[raindrop.id][1])
            if album_key:
                buckets[album_key].append(raindrop)

    clusters = []
    for album_key in sorted(buckets):
        unclaimed = sorted(buckets[album_key], key=lambda r: (r.created, r.id))
        while unclaimed:
            seed, *rest = unclaimed
            seed_artist = artists(parsed[seed.id][0])
            seed_tail = _tail_kept(parsed[seed.id][1])
            joined, unclaimed = [seed], []
            for candidate in rest:
                candidate_artist, candidate_album = parsed[candidate.id]
                if agree(seed_artist, artists(candidate_artist)) and (
                    _tail_kept(candidate_album) == seed_tail
                ):
                    joined.append(candidate)
                else:
                    unclaimed.append(candidate)
            if len(joined) >= 2:
                clusters.append(Cluster(matched_as=parsed[seed.id], raindrops=tuple(joined)))
    return clusters
