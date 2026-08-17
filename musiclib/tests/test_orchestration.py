import shutil
from pathlib import Path

import pytest

from musiclib.albumfile import load_album, new_album_doc, release_from_doc, save_album
from musiclib.preflight import Finding, is_blocked, observe

FIXTURE = Path(__file__).parent / "fixtures" / "silence.flac"


@pytest.fixture
def on_disk(tmp_path, make_image):
    """A real album directory: FLACs, project files, optionally a cover."""

    def _make(flacs=9, aup3=4, cover=None, name="daphni"):
        d = tmp_path / name
        d.mkdir()
        for i in range(1, flacs + 1):
            shutil.copy(FIXTURE, d / f"{i}.flac")
        for letter in "abcdefgh"[:aup3]:
            (d / f"{letter}.aup3").write_bytes(b"not really a project")
        if cover is not None:
            (d / "cover.jpg").write_bytes(cover)
        return d

    return _make


@pytest.mark.parametrize(
    "findings, expected",
    [
        ([], False),
        ([Finding("warn", "small cover")], False),
        ([Finding("stop", "count mismatch")], True),
        ([Finding("warn", "w"), Finding("stop", "s")], True),
    ],
    ids=["clean", "warning-only", "stop", "both"],
)
def test_only_a_stop_blocks_an_album(findings, expected):
    assert is_blocked(findings) is expected


def test_counts_what_is_actually_on_disk(on_disk, make_release):
    candidate = observe(on_disk(flacs=9, aup3=4), make_release())
    assert candidate.flac_count == 9
    assert candidate.aup3_count == 4
    assert candidate.slug == "daphni"


def test_measures_a_cover_that_is_present(on_disk, make_image, make_release):
    candidate = observe(on_disk(cover=make_image("JPEG", size=(1200, 1200))), make_release())
    assert candidate.cover is not None
    assert candidate.cover.width == 1200


def test_reports_no_cover_when_the_file_is_missing(on_disk, make_release):
    assert observe(on_disk(), make_release()).cover is None


def test_a_corrupt_cover_counts_as_no_cover(on_disk, make_release):
    """A truncated download must stop the album, not crash the run."""
    candidate = observe(on_disk(cover=b"<html>404</html>"), make_release())
    assert candidate.cover is None


def test_ignores_project_files_when_counting_tracks(on_disk, make_release):
    assert observe(on_disk(flacs=3, aup3=6), make_release()).flac_count == 3


def test_rebuilds_the_release_from_the_cached_snapshot(tmp_path, make_release):
    original = make_release(tracks=9, sides="ABCD", title="Cherry")
    path = tmp_path / "album.yaml"
    save_album(path, new_album_doc(26241443, "http://d", "http://c", original))

    assert release_from_doc(load_album(path)) == original


def test_an_album_with_no_snapshot_has_no_release(tmp_path):
    path = tmp_path / "album.yaml"
    save_album(path, new_album_doc(None, None, "http://c", None))
    assert release_from_doc(load_album(path)) is None


def test_no_document_at_all_has_no_release():
    assert release_from_doc(None) is None
