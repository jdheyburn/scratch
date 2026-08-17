import json

import pytest

from musiclib.cover import fetch_cover
from musiclib.discogs import discogs_token, fetch_release
from musiclib.errors import DiscogsError


@pytest.fixture
def fake_get():
    """A stand-in transport that records calls and replays canned responses."""

    class Get:
        def __init__(self):
            self.calls = []
            self.response = b""
            self.error = None

        def __call__(self, url, headers=None):
            self.calls.append((url, headers or {}))
            if self.error:
                raise self.error
            return self.response

    return Get()


def test_reads_the_token_from_the_beets_config(tmp_path):
    (tmp_path / "discogs_token.json").write_text(json.dumps({"token": "abc", "secret": "s"}))
    assert discogs_token(tmp_path) == "abc"


def test_a_missing_token_file_is_reported_clearly(tmp_path):
    with pytest.raises(DiscogsError, match="token"):
        discogs_token(tmp_path)


def test_asks_discogs_for_the_release_by_id(fake_get, make_payload):
    fake_get.response = json.dumps(make_payload()).encode()
    fetch_release(3897786, token="abc", get=fake_get)

    url, headers = fake_get.calls[0]
    assert url.endswith("/releases/3897786")
    assert headers["Authorization"] == "Discogs token=abc"


def test_identifies_itself_because_discogs_rejects_anonymous_agents(fake_get, make_payload):
    fake_get.response = json.dumps(make_payload()).encode()
    fetch_release(3897786, token="abc", get=fake_get)
    assert "musiclib" in fake_get.calls[0][1]["User-Agent"]


def test_returns_the_parsed_release(fake_get, make_payload):
    fake_get.response = json.dumps(make_payload()).encode()
    release = fetch_release(3897786, token="abc", get=fake_get)
    assert release.artist == "Daphni"
    assert release.tracks == 9


def test_a_release_that_does_not_exist_is_reported_not_crashed(fake_get):
    fake_get.error = RuntimeError("HTTP 404")
    with pytest.raises(DiscogsError, match="3897786"):
        fetch_release(3897786, token="abc", get=fake_get)


def test_nonsense_from_discogs_is_reported_not_crashed(fake_get):
    fake_get.response = b"<html>gateway timeout</html>"
    with pytest.raises(DiscogsError):
        fetch_release(1, token="abc", get=fake_get)


def test_fetches_and_normalises_the_cover(fake_get, make_image):
    fake_get.response = make_image("WEBP", size=(1200, 1200))
    cover, data = fetch_cover("http://example/art.webp", get=fake_get)
    assert (cover.width, cover.height) == (1200, 1200)
    assert data[:2] == b"\xff\xd8"


def test_a_cover_url_that_does_not_resolve_is_reported(fake_get):
    fake_get.error = RuntimeError("HTTP 403")
    with pytest.raises(DiscogsError, match=r"art\.jpg"):
        fetch_cover("http://example/art.jpg", get=fake_get)


def test_refuses_a_release_that_is_not_the_one_we_asked_for(fake_get, make_payload):
    """Discogs follows redirects for merged/replaced releases and answers 200
    with a different record. Trusting the body silently captures the wrong
    album under the right id."""
    fake_get.response = json.dumps(make_payload(id=999999, title="Seriously Disturbed")).encode()

    with pytest.raises(DiscogsError, match="999999"):
        fetch_release(37215042, token="abc", get=fake_get)


def test_the_error_names_the_release_we_asked_for(fake_get, make_payload):
    fake_get.response = json.dumps(make_payload(id=999999)).encode()
    with pytest.raises(DiscogsError, match="37215042"):
        fetch_release(37215042, token="abc", get=fake_get)


def test_a_matching_id_passes_through(fake_get, make_payload):
    fake_get.response = json.dumps(make_payload(id=3897786)).encode()
    assert fetch_release(3897786, token="abc", get=fake_get).artist == "Daphni"


def test_image_hosts_get_a_browser_user_agent(fake_get, make_image):
    """Shop CDNs (cloudfront and friends) answer 403 to a non-browser agent."""
    fake_get.response = make_image("JPEG")
    fetch_cover("http://cdn/art.jpg", get=fake_get)

    agent = fake_get.calls[0][1]["User-Agent"]
    assert "Mozilla" in agent


def test_the_discogs_api_still_gets_our_own_user_agent(fake_get, make_payload):
    """Discogs requires a descriptive agent identifying the application."""
    fake_get.response = json.dumps(make_payload(id=1)).encode()
    fetch_release(1, token="abc", get=fake_get)

    assert "musiclib" in fake_get.calls[0][1]["User-Agent"]
