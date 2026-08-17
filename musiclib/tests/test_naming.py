import pytest

from musiclib.errors import NotATrack
from musiclib.preflight import destination_name
from musiclib.tags import track_number_from_filename


@pytest.mark.parametrize(
    "filename, expected",
    [("1.flac", 1), ("9.flac", 9), ("10.flac", 10), ("16.flac", 16), ("01.flac", 1)],
)
def test_reads_the_track_number_out_of_the_filename(filename, expected):
    assert track_number_from_filename(filename) == expected


def test_orders_numerically_not_lexically():
    """Six albums in this batch have 10+ tracks, where lexical order lies."""
    names = ["10.flac", "2.flac", "1.flac", "9.flac"]
    assert sorted(names, key=track_number_from_filename) == [
        "1.flac",
        "2.flac",
        "9.flac",
        "10.flac",
    ]


@pytest.mark.parametrize("filename", ["a.aup3", "cover.jpg", "album.yaml", ".DS_Store"])
def test_rejects_files_that_are_not_numbered_tracks(filename):
    with pytest.raises(NotATrack, match=filename.replace(".", r"\.")):
        track_number_from_filename(filename)


def test_names_destination_from_release_and_id(make_release):
    release = make_release(artists=[{"name": "Daphni"}], title="Cherry")
    assert (
        destination_name(release, discogs_id=26241443, slug="daphni")
        == "Daphni - Cherry (26241443)"
    )


def test_replaces_path_separators_so_a_slash_cannot_nest_a_directory(make_release):
    release = make_release(artists=[{"name": "AC/DC"}], title="Back In Black")
    name = destination_name(release, discogs_id=400591, slug="acdc")
    assert "/" not in name
    assert name == "AC_DC - Back In Black (400591)"


def test_falls_back_to_the_slug_when_there_is_no_discogs_id():
    assert destination_name(None, discogs_id=None, slug="white label") == "white label (no-id)"
