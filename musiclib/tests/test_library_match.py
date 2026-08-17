import pytest

from musiclib.library import LibraryAlbum, choose_library_match


def album(albumid="919801", artist="Substance & Vainqueur", name="Reverberation", items=2):
    return LibraryAlbum(albumid=albumid, artist=artist, album=name, items=items)


def test_nothing_in_the_library_means_no_match():
    assert choose_library_match([], expected=2) is None


def test_a_single_album_with_the_right_track_count_is_the_match():
    """You picked a different pressing at the beets prompt — still your album."""
    match = album()
    assert choose_library_match([match], expected=2) is match


def test_a_single_album_with_the_wrong_track_count_is_not_the_match():
    assert choose_library_match([album(items=9)], expected=2) is None


def test_two_candidates_with_the_right_count_is_too_ambiguous_to_choose():
    """Never guess when archiving is the next step."""
    candidates = [album(albumid="1"), album(albumid="2")]
    assert choose_library_match(candidates, expected=2) is None


def test_the_one_with_the_matching_count_wins_over_one_that_disagrees():
    right = album(albumid="919801", items=2)
    wrong = album(albumid="36735403", items=9)
    assert choose_library_match([wrong, right], expected=2) is right


@pytest.mark.parametrize("expected", [0, None])
def test_an_unknown_expectation_never_matches(expected):
    assert choose_library_match([album()], expected=expected) is None
