"""Credentials on disk. Nothing here prints one."""

import pytest

from musictrack.config import load_bandcamp_cookie, load_spotify_credentials
from musictrack.errors import MissingToken


def test_a_missing_cookie_explains_how_to_make_one(tmp_path):
    with pytest.raises(MissingToken) as problem:
        load_bandcamp_cookie(tmp_path / "cookie")
    assert "bandcamp" in str(problem.value).lower()


def test_an_empty_cookie_is_treated_as_missing(tmp_path):
    path = tmp_path / "cookie"
    path.write_text("   \n")
    with pytest.raises(MissingToken):
        load_bandcamp_cookie(path)


def test_a_cookie_is_read_and_stripped(tmp_path):
    path = tmp_path / "cookie"
    path.write_text("identity=abc; js_logged_in=1\n")
    assert load_bandcamp_cookie(path) == "identity=abc; js_logged_in=1"


def test_spotify_needs_both_halves(tmp_path):
    (tmp_path / "client_id").write_text("id")
    with pytest.raises(MissingToken) as problem:
        load_spotify_credentials(tmp_path)
    assert "client_secret" in str(problem.value)


def test_spotify_credentials_are_read_as_a_pair(tmp_path):
    (tmp_path / "client_id").write_text("id\n")
    (tmp_path / "client_secret").write_text("secret\n")
    assert load_spotify_credentials(tmp_path) == ("id", "secret")


def test_no_credential_value_appears_in_the_error(tmp_path):
    """A message that quotes the secret ends up in a terminal scrollback."""
    (tmp_path / "client_id").write_text("SUPERSECRETID")
    with pytest.raises(MissingToken) as problem:
        load_spotify_credentials(tmp_path)
    assert "SUPERSECRETID" not in str(problem.value)
