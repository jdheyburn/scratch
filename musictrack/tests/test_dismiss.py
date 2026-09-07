"""Recording a decision from the command line."""

import pytest
import typer
from typer.testing import CliRunner

from musictrack.cli import app
from musictrack.commands.dismiss import split_row_id
from musictrack.store import Dismissals


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


def test_dismiss_writes_a_row_with_source_ref_and_reason(tmp_path, monkeypatch):
    """Dismissing bandcamp-wishlist:123 with a reason writes to the store."""
    monkeypatch.setattr(
        "musictrack.commands.dismiss.Dismissals", lambda: Dismissals(tmp_path / "test.db")
    )

    runner = CliRunner()
    result = runner.invoke(app, ["dismiss", "bandcamp-wishlist:123", "--reason", "duplicate"])
    assert result.exit_code == 0
    assert "dismissed" in result.stdout

    store = Dismissals(tmp_path / "test.db")
    hidden = store.hidden()
    assert ("bandcamp-wishlist", "123") in hidden
    assert hidden[("bandcamp-wishlist", "123")] == "duplicate"


def test_dismiss_stores_empty_reason_when_no_reason_given(tmp_path, monkeypatch):
    """Dismissing without --reason stores empty string, readable as a dismissal."""
    monkeypatch.setattr(
        "musictrack.commands.dismiss.Dismissals", lambda: Dismissals(tmp_path / "test.db")
    )

    runner = CliRunner()
    result = runner.invoke(app, ["dismiss", "spotify:abc123"])
    assert result.exit_code == 0

    store = Dismissals(tmp_path / "test.db")
    hidden = store.hidden()
    assert ("spotify", "abc123") in hidden
    assert hidden[("spotify", "abc123")] == ""


def test_dismiss_round_trips_a_ref_containing_colon(tmp_path, monkeypatch):
    """A ref with colons in it: dismiss it, then find it under the full key."""
    monkeypatch.setattr(
        "musictrack.commands.dismiss.Dismissals", lambda: Dismissals(tmp_path / "test.db")
    )

    runner = CliRunner()
    result = runner.invoke(app, ["dismiss", "spotify:spotify:album:xyz:ref"])
    assert result.exit_code == 0

    store = Dismissals(tmp_path / "test.db")
    hidden = store.hidden()
    assert ("spotify", "spotify:album:xyz:ref") in hidden


def test_malformed_row_id_exits_non_zero_and_writes_nothing(tmp_path, monkeypatch):
    """A malformed row id fails cleanly and does not write."""
    monkeypatch.setattr(
        "musictrack.commands.dismiss.Dismissals", lambda: Dismissals(tmp_path / "test.db")
    )

    runner = CliRunner()
    result = runner.invoke(app, ["dismiss", "nocolon"])
    assert result.exit_code != 0

    store = Dismissals(tmp_path / "test.db")
    hidden = store.hidden()
    assert len(hidden) == 0
