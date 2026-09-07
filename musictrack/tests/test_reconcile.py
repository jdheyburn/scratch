"""Turning verdicts into a report."""

from musictrack.commands.reconcile import classify
from musictrack.match import LibraryIndex
from musictrack.models import AlbumRef


def album(artist, title):
    return AlbumRef(source="beets", artist=artist, album=title, ref="")


def want(artist, title, ref="1", source="bandcamp-wishlist"):
    return AlbumRef(source=source, artist=artist, album=title, ref=ref)


def library():
    return LibraryIndex(albums=[album("Theo Parrish", "Parallel Dimensions")], tracks=[])


def test_each_candidate_lands_in_exactly_one_bucket():
    report = classify(
        [want("Theo Parrish", "Parallel Dimensions"), want("Lucy Gooch", "Rushing", ref="2")],
        library(),
        {},
    )
    assert len(report.owned) == 1
    assert len(report.absent) == 1
    assert len(report.possible) == 0


def test_a_dismissed_row_is_left_out():
    hidden = {("bandcamp-wishlist", "1"): "own the digital, want the vinyl"}
    report = classify([want("Theo Parrish", "Parallel Dimensions")], library(), hidden)
    assert report.owned == []


def test_a_dismissal_only_hides_its_own_source():
    hidden = {("spotify", "1"): "no"}
    report = classify([want("Theo Parrish", "Parallel Dimensions")], library(), hidden)
    assert len(report.owned) == 1


def test_the_report_keeps_the_library_album_that_matched():
    report = classify([want("Theo Parrish", "Parallel Dimensions")], library(), {})
    _, match = report.owned[0]
    assert match.library is not None
    assert match.library.album == "Parallel Dimensions"
