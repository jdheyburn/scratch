import pytest

from musiclib.discogs import extract_release_id


@pytest.mark.parametrize(
    "typed",
    [
        "3897786",
        "r3897786",
        "[r3897786]",
        "https://www.discogs.com/release/3897786-Daphni-Jiaolong",
        "https://www.discogs.com/fr/release/3897786-Daphni-Jiaolong",
        "  3897786  ",
    ],
)
def test_accepts_every_form_you_might_paste(typed):
    assert extract_release_id(typed) == 3897786


@pytest.mark.parametrize("typed", ["", "   ", "daphni", "https://www.discogs.com/master/12345"])
def test_returns_none_for_things_that_are_not_a_release(typed):
    assert extract_release_id(typed) is None
