import pytest

from musiclib.albumfile import load_album, new_album_doc, save_album


@pytest.fixture
def written(tmp_path, make_release):
    """An album.yaml on disk, plus its path."""

    def _write(release=None, **doc_overrides):
        # `release=False` means "no release at all"; the default means "a normal one".
        release = (
            make_release(tracks=2, sides="AB", title="Cherry", year=2022)
            if release is None
            else (release or None)
        )
        path = tmp_path / "album.yaml"
        fields = {
            "discogs_id": 26241443,
            "discogs_url": "http://d/26241443",
            "cover_url": "http://c.jpg",
            **doc_overrides,
        }
        save_album(path, new_album_doc(release=release, **fields))
        return path

    return _write


def test_a_new_document_records_what_you_typed(written):
    doc = load_album(written())
    assert doc["discogs_id"] == 26241443
    assert doc["cover_url"] == "http://c.jpg"


def test_a_new_document_snapshots_the_release(written):
    doc = load_album(written())
    assert doc["release"]["artist"] == "Daphni"
    assert doc["release"]["album"] == "Cherry"
    assert doc["release"]["tracks"] == 2
    assert doc["release"]["side_tracks"] == {"A": 1, "B": 1}


def test_the_generated_header_names_the_release(written):
    assert "Daphni" in written().read_text().splitlines()[0]


def test_an_album_with_no_release_omits_the_snapshot(written):
    doc = load_album(written(release=False, discogs_id=None, discogs_url=None))
    assert "release" not in doc
    assert doc["discogs_id"] is None


def test_a_comment_you_added_by_hand_survives_a_rewrite(written):
    """The whole reason for ruamel over PyYAML."""
    path = written()
    path.write_text(path.read_text() + "\n# side D has a locked groove, ignore it\n")

    doc = load_album(path)
    doc["discogs_id"] = 999
    save_album(path, doc)

    assert "locked groove" in path.read_text()
    assert load_album(path)["discogs_id"] == 999


def test_key_order_is_stable_across_a_rewrite(written):
    path = written()
    before = [line.split(":")[0] for line in path.read_text().splitlines() if ":" in line]

    doc = load_album(path)
    doc["discogs_id"] = 999
    save_album(path, doc)

    after = [line.split(":")[0] for line in path.read_text().splitlines() if ":" in line]
    assert before == after
