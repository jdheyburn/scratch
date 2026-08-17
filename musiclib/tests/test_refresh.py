import io
import json

import pytest
from PIL import Image

from musiclib.albumfile import load_album, new_album_doc, save_album
from musiclib.capture import refresh_album


@pytest.fixture
def transport(make_payload, make_image):
    class Get:
        def __init__(self):
            self.payload = make_payload(title="Cherry", artists=[{"name": "Daphni"}])
            self.image = make_image("PNG", size=(2000, 2000))
            self.urls = []

        def __call__(self, url, headers=None):
            self.urls.append(url)
            if "api.discogs.com" in url:
                # Answer as the real API does: with the release requested.
                asked = int(url.rsplit("/", 1)[1])
                return json.dumps({**self.payload, "id": asked}).encode()
            return self.image

    return Get()


@pytest.fixture
def album(tmp_path, make_release, make_image):
    d = tmp_path / "daphni"
    d.mkdir()
    save_album(
        d / "album.yaml",
        new_album_doc(3897786, "http://d/3897786", "http://art/small.jpg", make_release()),
    )
    (d / "cover.jpg").write_bytes(make_image("JPEG", size=(700, 700)))
    return d


def test_a_hand_edited_id_pulls_a_fresh_snapshot(album, transport):
    doc = load_album(album / "album.yaml")
    doc["discogs_id"] = 26241443
    save_album(album / "album.yaml", doc)

    refresh_album(album, token="abc", get=transport)

    updated = load_album(album / "album.yaml")
    assert updated["release"]["album"] == "Cherry"
    assert f"{DISCOGS_ID}" in transport.urls[0]


DISCOGS_ID = 26241443


def test_a_hand_edited_cover_url_is_refetched(album, transport):
    doc = load_album(album / "album.yaml")
    doc["cover_url"] = "http://art/big.jpg"
    save_album(album / "album.yaml", doc)

    refresh_album(album, token="abc", get=transport)

    with Image.open(io.BytesIO((album / "cover.jpg").read_bytes())) as im:
        assert im.size == (2000, 2000)


def test_refreshing_upgrades_a_bandcamp_url_in_place(album, transport):
    doc = load_album(album / "album.yaml")
    doc["cover_url"] = "https://f4.bcbits.com/img/a123_16.jpg"
    save_album(album / "album.yaml", doc)

    refresh_album(album, token="abc", get=transport)

    assert load_album(album / "album.yaml")["cover_url"].endswith("_0.jpg")


def test_your_comments_survive_a_refresh(album, transport):
    path = album / "album.yaml"
    path.write_text(path.read_text() + "\n# bought at Phonica, sleeve is battered\n")

    refresh_album(album, token="abc", get=transport)

    assert "Phonica" in path.read_text()


def test_an_album_with_no_id_still_refreshes_its_cover(album, transport):
    doc = load_album(album / "album.yaml")
    doc["discogs_id"] = None
    del doc["release"]
    save_album(album / "album.yaml", doc)

    assert refresh_album(album, token="abc", get=transport) is True
    assert not any("api.discogs.com" in u for u in transport.urls)


def test_an_album_with_no_document_cannot_be_refreshed(tmp_path, transport):
    (tmp_path / "empty").mkdir()
    assert refresh_album(tmp_path / "empty", token="abc", get=transport) is False


def test_the_generated_comment_names_the_command_that_actually_refetches(album):
    """The file used to promise a re-fetch that no code performed."""
    text = (album / "album.yaml").read_text()
    assert "--refresh" in text
