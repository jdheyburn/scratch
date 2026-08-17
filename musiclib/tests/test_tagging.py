import shutil
from pathlib import Path

import mutagen.flac
import pytest

from musiclib.tags import tag_album

FIXTURE = Path(__file__).parent / "fixtures" / "silence.flac"


@pytest.fixture
def album_dir(tmp_path):
    """A real album directory of real (tiny) FLACs."""

    def _make(count=3, name="daphni"):
        d = tmp_path / name
        d.mkdir()
        for i in range(1, count + 1):
            shutil.copy(FIXTURE, d / f"{i}.flac")
        return d

    return _make


def read_tags(path):
    return {k.upper(): v[0] for k, v in (mutagen.flac.FLAC(path).tags or {}).items()}


def test_writes_the_release_id_to_every_track(album_dir):
    d = album_dir(count=3)
    tag_album(d, discogs_id=26241443)
    for f in d.glob("*.flac"):
        assert read_tags(f)["MUSICBRAINZ_ALBUMID"] == "26241443"


def test_writes_the_track_number_matching_the_filename(album_dir):
    d = album_dir(count=12)
    tag_album(d, discogs_id=26241443)
    assert read_tags(d / "10.flac")["TRACKNUMBER"] == "10"
    assert read_tags(d / "2.flac")["TRACKNUMBER"] == "2"


def test_reports_how_many_tracks_it_tagged(album_dir):
    assert tag_album(album_dir(count=5), discogs_id=1) == 5


def test_an_album_with_no_release_gets_track_numbers_only(album_dir):
    d = album_dir(count=2)
    tag_album(d, discogs_id=None)
    tags = read_tags(d / "1.flac")
    assert tags["TRACKNUMBER"] == "1"
    assert "MUSICBRAINZ_ALBUMID" not in tags


def test_leaves_unrelated_tags_alone(album_dir):
    d = album_dir(count=1)
    tag_album(d, discogs_id=1)
    assert "ENCODER" in read_tags(d / "1.flac")


def test_tagging_twice_leaves_the_same_result(album_dir):
    d = album_dir(count=2)
    tag_album(d, discogs_id=26241443)
    first = read_tags(d / "1.flac")
    tag_album(d, discogs_id=26241443)
    assert read_tags(d / "1.flac") == first


def test_a_corrected_id_replaces_the_old_one_rather_than_appending(album_dir):
    d = album_dir(count=1)
    tag_album(d, discogs_id=111)
    tag_album(d, discogs_id=222)
    tags = mutagen.flac.FLAC(d / "1.flac").tags
    assert tags["musicbrainz_albumid"] == ["222"]


def test_ignores_files_that_are_not_numbered_tracks(album_dir):
    d = album_dir(count=2)
    shutil.copy(FIXTURE, d / "outtake.flac")
    assert tag_album(d, discogs_id=1) == 2


def test_writes_the_album_and_albumartist_from_the_release(album_dir, make_release):
    d = album_dir(count=2)
    release = make_release(artists=[{"name": "Wax (4)"}], title="No. 90009")
    tag_album(d, discogs_id=30257615, release=release)

    tags = read_tags(d / "1.flac")
    assert tags["ALBUM"] == "No. 90009"
    assert tags["ALBUMARTIST"] == "Wax"
    assert "TITLE" not in tags


def test_the_tags_are_readable_by_the_library_beets_uses(album_dir, make_release):
    """Written with mutagen, read back with mediafile — beets' own tag layer.

    Without year/catalogue/media/label, a repressing that shares artist, album
    and track count outranks the exact release we asked for: measured 7th of 10.
    """
    import mediafile

    d = album_dir(count=1)
    release = make_release(
        artists=[{"name": "Substance (2)"}],
        title="Reverberation / Reverberate",
        year=2026,
        labels=[{"name": "Scion Versions", "catno": "SV 02"}],
        formats=[{"name": "Vinyl"}],
    )
    tag_album(d, discogs_id=36735403, release=release)

    mf = mediafile.MediaFile(d / "1.flac")
    assert mf.mb_albumid == "36735403"
    assert mf.album == "Reverberation / Reverberate"
    assert mf.albumartist == "Substance"
    assert mf.year == 2026
    assert mf.catalognum == "SV 02"
    assert mf.media == "Vinyl"
    assert mf.label == "Scion Versions"
    # Still no per-track titles: a mis-split would make those wrong.
    assert mf.title != "Reverberation / Reverberate"
