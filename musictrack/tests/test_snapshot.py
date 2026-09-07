"""The rules, against the whole 2026-09-03 capture.

These counts are the spec's evidence table. A rule change that moves them is a
deliberate act, and this test is where it has to be argued for.
"""

import json
from pathlib import Path

import pytest

from musictrack.commands.reconcile import classify
from musictrack.match import LibraryIndex
from musictrack.models import AlbumRef
from musictrack.sources.bandcamp import to_ref
from musictrack.sources.library import DELIMITER
from musictrack.sources.spotify import album_blocks

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture(scope="module")
def library():
    albums, tracks = [], []
    for line in (FIXTURES / "beets_albums.txt").read_text().splitlines():
        parts = line.split(DELIMITER)
        if len(parts) == 2:
            albums.append(AlbumRef("beets", parts[0], parts[1], ""))
    for line in (FIXTURES / "beets_tracks.txt").read_text().splitlines():
        parts = line.split(DELIMITER)
        if len(parts) == 2:
            tracks.append(AlbumRef("beets-track", parts[0], parts[1], ""))
    return LibraryIndex(albums=albums, tracks=tracks)


@pytest.mark.parametrize(
    "name, source, expected",
    [
        ("bandcamp_wishlist.json", "bandcamp-wishlist", (845, 6, 19, 820)),
        ("bandcamp_collection.json", "bandcamp-collection", (377, 338, 29, 10)),
    ],
)
def test_the_bandcamp_buckets_are_where_the_spec_says(library, name, source, expected):
    refs = [to_ref(item, source) for item in load(name)]
    report = classify(refs, library, {})
    total, owned, possible, absent = expected
    assert len(refs) == total
    assert (len(report.owned), len(report.possible), len(report.absent)) == (
        owned,
        possible,
        absent,
    )


def test_the_spotify_buckets_are_where_the_spec_says(library):
    refs = album_blocks(load("spotify_tolisten.json"))
    report = classify(refs, library, {})
    assert len(refs) == 675
    assert (len(report.owned), len(report.possible), len(report.absent)) == (19, 15, 641)
