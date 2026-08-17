import json
import shutil
from pathlib import Path

import pytest

from musiclib.albumfile import load_album
from musiclib.capture import capture
from musiclib.preflight import Candidate, is_blocked, preflight

FIXTURE = Path(__file__).parent / "fixtures" / "silence.flac"


@pytest.fixture
def directory(tmp_path):
    d = tmp_path / "daphni"
    d.mkdir()
    for i in range(1, 10):
        shutil.copy(FIXTURE, d / f"{i}.flac")
    return d


@pytest.fixture
def answers():
    """Scripted replies, consumed in order."""

    class Ask:
        def __init__(self):
            self.queue = []
            self.prompts = []

        def __call__(self, prompt, **_):
            self.prompts.append(prompt)
            return self.queue.pop(0)

    return Ask()


@pytest.fixture
def transport(make_payload, make_image):
    """Serves release JSON for api.discogs.com and image bytes for anything else."""

    class Get:
        def __init__(self):
            self.payload = make_payload()
            self.image = make_image("PNG", size=(1200, 1200))
            self.urls = []

        def __call__(self, url, headers=None):
            self.urls.append(url)
            if "api.discogs.com" in url:
                # Answer as the real API does: with the release requested.
                asked = int(url.rsplit("/", 1)[1])
                return json.dumps({**self.payload, "id": asked}).encode()
            return self.image

    return Get()


def run(directory, answers, transport, confirm=lambda *a, **k: True):
    return capture(
        directory, token="abc", get=transport, ask=answers, confirm=confirm, echo=lambda *a: None
    )


def test_writes_an_album_yaml_from_what_you_typed(directory, answers, transport):
    answers.queue = ["3897786", "http://art/cover.png"]
    assert run(directory, answers, transport) is True

    doc = load_album(directory / "album.yaml")
    assert doc["discogs_id"] == 3897786
    assert doc["release"]["artist"] == "Daphni"


def test_saves_the_cover_as_real_jpeg_next_to_the_tracks(directory, answers, transport):
    answers.queue = ["3897786", "http://art/cover.png"]
    run(directory, answers, transport)

    cover = directory / "cover.jpg"
    assert cover.is_file()
    assert cover.read_bytes()[:2] == b"\xff\xd8"


def test_accepts_a_pasted_url_for_the_release(directory, answers, transport):
    answers.queue = ["https://www.discogs.com/release/3897786-Daphni", "http://art/c.png"]
    run(directory, answers, transport)
    assert load_album(directory / "album.yaml")["discogs_id"] == 3897786


def test_reprompts_when_what_you_typed_is_not_a_release(directory, answers, transport):
    answers.queue = ["not a release", "3897786", "http://art/c.png"]
    run(directory, answers, transport)
    assert load_album(directory / "album.yaml")["discogs_id"] == 3897786


def test_reprompts_when_you_reject_the_release_it_found(directory, answers, transport):
    answers.queue = ["111", "3897786", "http://art/c.png"]
    replies = iter([False, True])
    run(directory, answers, transport, confirm=lambda *a, **k: next(replies))
    assert load_album(directory / "album.yaml")["discogs_id"] == 3897786


def test_skipping_records_no_release_but_still_wants_a_cover(directory, answers, transport):
    answers.queue = ["skip", "http://art/c.png"]
    assert run(directory, answers, transport) is True

    doc = load_album(directory / "album.yaml")
    assert doc["discogs_id"] is None
    assert "release" not in doc
    assert (directory / "cover.jpg").is_file()


def test_reprompts_when_the_cover_url_does_not_resolve(directory, answers, transport):
    def flaky(url, headers=None):
        if url.endswith("bad.png"):
            raise RuntimeError("HTTP 404")
        return transport(url, headers)

    answers.queue = ["3897786", "http://art/bad.png", "http://art/good.png"]
    assert run(directory, answers, flaky) is True
    assert (directory / "cover.jpg").is_file()


def test_skipping_the_cover_keeps_the_release_you_just_confirmed(directory, answers, transport):
    """Losing a confirmed release because the artwork 403'd is unacceptable —
    it throws away the one thing that took effort to find."""
    answers.queue = ["3897786", "skip"]
    assert run(directory, answers, transport) is True

    doc = load_album(directory / "album.yaml")
    assert doc["discogs_id"] == 3897786
    assert doc["cover_url"] is None
    assert not (directory / "cover.jpg").exists()


def test_an_empty_cover_answer_is_the_same_as_skipping(directory, answers, transport):
    answers.queue = ["3897786", ""]
    assert run(directory, answers, transport) is True
    assert load_album(directory / "album.yaml")["discogs_id"] == 3897786


def test_an_album_captured_without_a_cover_is_stopped_by_preflight(directory, answers, transport):
    """Skipping records the release; it does not wave the album through."""
    answers.queue = ["3897786", "skip"]
    run(directory, answers, transport)

    findings = preflight(
        Candidate(slug="daphni", flac_count=9, aup3_count=4, release=None, cover=None)
    )
    assert is_blocked(findings)


def test_asks_bandcamp_for_the_full_size_artwork(directory, answers, transport):
    """A pasted _16 url is the 700px variant; _0 is the original upload."""
    answers.queue = ["3897786", "https://f4.bcbits.com/img/a3990828446_16.jpg"]
    run(directory, answers, transport)

    assert transport.urls[-1] == "https://f4.bcbits.com/img/a3990828446_0.jpg"
    assert load_album(directory / "album.yaml")["cover_url"].endswith("_0.jpg")


def test_the_confirmation_shows_the_id_it_actually_fetched(directory, answers, transport):
    """So a release that isn't the one you pasted is obvious before you say yes."""
    lines = []
    answers.queue = ["3897786", "http://art/c.png"]
    capture(
        directory,
        token="abc",
        get=transport,
        ask=answers,
        confirm=lambda *a, **k: True,
        echo=lines.append,
    )
    assert any("3897786" in str(line) for line in lines)
