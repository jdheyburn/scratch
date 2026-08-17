"""Resolving a Discogs release id into the facts the rest of the pipeline needs."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from musiclib.errors import DiscogsError
from musiclib.net import USER_AGENT, http_get

DISCOGS_API = "https://api.discogs.com"
BEETS_CONFIG_DIR = Path.home() / ".config" / "beets"

# Discogs appends " (2)", " (3)" etc. to disambiguate artists sharing a name.
_ARTIST_SUFFIX = re.compile(r"\s\(\d+\)$")
# Vinyl positions look like A1, B2, C10 — or bare A/B on a single. Anchored at
# both ends so a disc position like CD1 isn't read as side C.
_SIDE_POSITION = re.compile(r"^([A-Za-z])\d*$")
# The same shapes beets itself accepts: bare id, r123, [r123], or a release URL.
_RELEASE_ID = re.compile(r"(?:^|\[?r|discogs\.com/(?:[^/]+/)?release/)(\d+)\b")


@dataclass(frozen=True)
class Release:
    """The parts of a Discogs release this pipeline cares about."""

    artist: str
    album: str
    year: int | None
    label: str | None
    catalogue: str | None
    format: str | None
    tracks: int
    sides: int | None
    side_tracks: dict[str, int] | None


def extract_release_id(typed: str) -> int | None:
    """Pull a Discogs release id out of whatever you pasted at the prompt."""
    match = _RELEASE_ID.search(typed.strip())
    return int(match[1]) if match else None


def _strip_suffix(name: str | None) -> str | None:
    """Remove Discogs' " (2)" disambiguator from an artist or label name."""
    return _ARTIST_SUFFIX.sub("", name) if name else name


def parse_release(payload: dict) -> Release:
    """Turn a Discogs API release payload into the fields we validate against."""
    # Skip anonymous entries rather than joining a None into the artist string.
    names = [n for a in payload.get("artists", []) if (n := _strip_suffix(a.get("name")))]
    positions = [
        t.get("position", "") for t in payload.get("tracklist", []) if t.get("type_") == "track"
    ]

    side_counts = Counter(m.group(1).upper() for p in positions if (m := _SIDE_POSITION.match(p)))
    # Partial side lettering means we can't trust the breakdown, so report none.
    sides_known = bool(side_counts) and sum(side_counts.values()) == len(positions)

    labels = payload.get("labels") or [{}]
    formats = payload.get("formats") or [{}]

    return Release(
        artist=" & ".join(names),
        album=payload.get("title", ""),
        year=payload.get("year") or None,
        label=_strip_suffix(labels[0].get("name")),
        catalogue=labels[0].get("catno"),
        format=formats[0].get("name"),
        tracks=len(positions),
        sides=len(side_counts) if sides_known else None,
        side_tracks=dict(sorted(side_counts.items())) if sides_known else None,
    )


def discogs_token(config_dir: Path = BEETS_CONFIG_DIR) -> str:
    """Reuse the token beets already has — no second credential to manage."""
    path = config_dir / "discogs_token.json"
    try:
        data = json.loads(path.read_text())
    except OSError as e:
        raise DiscogsError(f"no discogs token at {path}: {e}") from None
    token = data.get("token") or data.get("user_token")
    if not token:
        raise DiscogsError(f"no usable token in {path}")
    return token


def fetch_release(release_id: int, token: str, get=http_get) -> Release:
    url = f"{DISCOGS_API}/releases/{release_id}"
    headers = {"Authorization": f"Discogs token={token}", "User-Agent": USER_AGENT}
    try:
        payload = json.loads(get(url, headers))
    except json.JSONDecodeError:
        raise DiscogsError(f"discogs returned something that isn't a release ({url})") from None
    except Exception as e:
        raise DiscogsError(f"could not fetch release {release_id}: {e}") from None

    # Discogs redirects merged or replaced releases and answers 200 with a
    # different record. Without this check we'd capture the wrong album under
    # the id you typed, and you'd only notice at the beets prompt.
    returned = payload.get("id")
    if returned is not None and int(returned) != int(release_id):
        raise DiscogsError(
            f"asked discogs for release {release_id} but it returned {returned} "
            f"({payload.get('title', 'unknown')}) — the release was probably "
            f"merged or replaced; check the id on discogs"
        )
    return parse_release(payload)
