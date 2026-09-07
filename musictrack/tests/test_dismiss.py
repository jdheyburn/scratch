"""Recording a decision from the command line."""

import pytest
import typer

from musictrack.commands.dismiss import split_row_id


def test_a_row_id_splits_into_source_and_ref():
    assert split_row_id("bandcamp-wishlist:123") == ("bandcamp-wishlist", "123")


def test_a_spotify_ref_containing_no_colon_still_works():
    assert split_row_id("spotify:0alGk3J7TkTRGLaB9jbsCJ") == (
        "spotify",
        "0alGk3J7TkTRGLaB9jbsCJ",
    )


def test_a_ref_containing_a_colon_keeps_it():
    """Only the first colon separates; the rest belongs to the ref."""
    assert split_row_id("spotify:spotify:album:xyz") == ("spotify", "spotify:album:xyz")


@pytest.mark.parametrize("bad", ["", "nocolon", ":123", "source:"])
def test_a_malformed_row_id_is_rejected(bad):
    with pytest.raises(typer.BadParameter):
        split_row_id(bad)
