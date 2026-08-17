import pytest

from musiclib.discogs import parse_release


def test_reads_the_headline_release_fields(make_payload):
    r = parse_release(make_payload())
    assert (r.artist, r.album, r.year) == ("Daphni", "Jiaolong", 2012)
    assert (r.label, r.catalogue) == ("Jiaolong", "JIAOLONG005LP")


def test_counts_only_real_tracks_ignoring_side_headings(make_payload):
    tracklist = [
        {"position": "", "type_": "heading", "title": "Side A"},
        {"position": "A1", "type_": "track", "title": "One"},
        {"position": "A2", "type_": "track", "title": "Two"},
        {"position": "", "type_": "heading", "title": "Side B"},
        {"position": "B1", "type_": "track", "title": "Three"},
    ]
    assert parse_release(make_payload(tracklist=tracklist)).tracks == 3


def test_derives_sides_from_lettered_positions(make_payload):
    r = parse_release(make_payload())
    assert r.sides == 4
    assert r.side_tracks == {"A": 2, "B": 2, "C": 2, "D": 3}


@pytest.mark.parametrize(
    "positions, sides, side_tracks",
    [
        # A 7" lists its sides as bare letters, with no track number.
        (["A", "B"], 2, {"A": 1, "B": 1}),
        (["A"], 1, {"A": 1}),
        (["A1", "A2", "B1"], 2, {"A": 2, "B": 1}),
        # Digital-style numbering carries no side information.
        (["1", "2"], None, None),
        # A disc position must not be mistaken for side C.
        (["CD1", "CD2"], None, None),
        # Half-lettered means we can't trust the breakdown at all.
        (["A1", "2"], None, None),
    ],
    ids=["bare-letters", "one-sided", "lettered", "numeric", "disc", "mixed"],
)
def test_derives_sides_from_position_style(make_payload, positions, sides, side_tracks):
    tracklist = [{"position": p, "type_": "track", "title": p} for p in positions]
    r = parse_release(make_payload(tracklist=tracklist))
    assert r.sides == sides
    assert r.side_tracks == side_tracks


@pytest.mark.parametrize(
    "artists, expected",
    [
        ([{"name": "Daphni"}], "Daphni"),
        # Discogs appends (2), (3)… to disambiguate artists sharing a name.
        ([{"name": "Substance (2)"}], "Substance"),
        ([{"name": "Substance (2)"}, {"name": "Vainqueur"}], "Substance & Vainqueur"),
    ],
    ids=["plain", "disambiguated", "collaboration"],
)
def test_reads_artist_names(make_payload, artists, expected):
    assert parse_release(make_payload(artists=artists)).artist == expected


@pytest.mark.parametrize(
    "labels, expected",
    [
        ([{"name": "Jiaolong", "catno": "J005"}], "Jiaolong"),
        # Discogs disambiguates labels the same way it disambiguates artists.
        ([{"name": "Wax (4)", "catno": "WAX 90009"}], "Wax"),
        ([{"name": "Mute (2)", "catno": "X"}], "Mute"),
    ],
    ids=["plain", "wax-4", "mute-2"],
)
def test_strips_the_disambiguation_suffix_from_label_names(make_payload, labels, expected):
    assert parse_release(make_payload(labels=labels)).label == expected
