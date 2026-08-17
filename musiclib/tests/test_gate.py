import pytest

from musiclib.library import gate_verdict


def test_a_fully_imported_album_passes():
    assert gate_verdict(albums=1, files=["OK", "OK"], expected=2) is None


def test_an_album_beets_never_imported_is_refused():
    """Skipping at the beets prompt must not look like success."""
    verdict = gate_verdict(albums=0, files=[], expected=9)
    assert verdict is not None
    assert "not in the library" in verdict


@pytest.mark.parametrize("found, expected", [(1, 2), (3, 2), (11, 12)])
def test_a_count_that_disagrees_is_refused(found, expected):
    verdict = gate_verdict(albums=1, files=["OK"] * found, expected=expected)
    assert verdict is not None
    assert str(found) in verdict and str(expected) in verdict


def test_a_library_entry_whose_file_vanished_is_refused():
    verdict = gate_verdict(albums=1, files=["OK", "MISS"], expected=2)
    assert verdict is not None
    assert "missing" in verdict


def test_counts_how_many_files_are_missing():
    verdict = gate_verdict(albums=1, files=["OK", "MISS", "MISS"], expected=3)
    assert verdict is not None
    assert "2" in verdict


def test_an_album_with_nothing_expected_is_refused():
    """A zero expectation means we never recorded a transfer — don't archive."""
    assert gate_verdict(albums=1, files=[], expected=0) is not None
