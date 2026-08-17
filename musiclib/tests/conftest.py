"""Shared factories.

Each is a fixture returning a *callable*, so a test can still override a single
field inline — `make_candidate(flac_count=16)` — which a plain value fixture
can't do.
"""

import io

import pytest
from PIL import Image

from musiclib.cover import Cover
from musiclib.discogs import parse_release
from musiclib.preflight import Candidate


@pytest.fixture
def make_payload():
    """A Discogs release payload, shaped like the real API response."""

    def _make(**overrides):
        base = {
            "id": 3897786,
            "title": "Jiaolong",
            "year": 2012,
            "artists": [{"name": "Daphni"}],
            "labels": [{"name": "Jiaolong", "catno": "JIAOLONG005LP"}],
            "formats": [{"name": "Vinyl"}],
            "tracklist": [
                {"position": p, "type_": "track", "title": t}
                for p, t in [
                    ("A1", "Yes, I Know"),
                    ("A2", "Ne Noya"),
                    ("B1", "Ye Ye"),
                    ("B2", "Light"),
                    ("C1", "Pairs"),
                    ("C2", "Ahora"),
                    ("D1", "Jiao"),
                    ("D2", "Springs"),
                    ("D3", "Long"),
                ]
            ],
        }
        return {**base, **overrides}

    return _make


@pytest.fixture
def make_tracklist():
    """`tracks` tracks spread across `sides`; sides="" gives numeric positions."""

    def _make(tracks=9, sides="ABCD"):
        return [
            {
                "position": f"{sides[i % len(sides)]}{i}" if sides else str(i + 1),
                "type_": "track",
                "title": f"t{i}",
            }
            for i in range(tracks)
        ]

    return _make


@pytest.fixture
def make_release(make_payload, make_tracklist):
    def _make(tracks=9, sides="ABCD", **overrides):
        overrides.setdefault("tracklist", make_tracklist(tracks, sides))
        return parse_release(make_payload(**overrides))

    return _make


@pytest.fixture
def make_candidate(make_release):
    def _make(**overrides):
        base = dict(
            slug="daphni",
            flac_count=9,
            aup3_count=4,
            release=make_release(),
            cover=Cover(width=1200, height=1200),
        )
        return Candidate(**{**base, **overrides})

    return _make


@pytest.fixture
def make_image():
    def _make(fmt="PNG", size=(1200, 1200), mode="RGB"):
        buf = io.BytesIO()
        Image.new(mode, size, "red").save(buf, format=fmt)
        return buf.getvalue()

    return _make
