"""The shell snippet `reconcile` runs on the music server.

Run under a real zsh, because that's dee's login shell and zsh is where this
snippet goes wrong: a glob that matches nothing is an error there, not an empty
loop. Testing the string alone would have proved nothing.
"""

import shutil
import subprocess

import pytest

from musiclib.remote import pending_listing_command

SHELLS = [s for s in ("zsh", "bash", "sh") if shutil.which(s)]

pytestmark = pytest.mark.skipif(not SHELLS, reason="needs a shell to run the snippet in")


@pytest.fixture(params=SHELLS)
def shell(request):
    """zsh is what dee actually uses; the others prove the fix isn't a zsh trick."""
    return request.param


@pytest.fixture
def listing(shell):
    """Run the snippet as dee would, and parse what it prints."""

    def _run(directory):
        result = subprocess.run(
            [shell, "-c", pending_listing_command(str(directory))],
            capture_output=True,
            text=True,
        )
        return _parse(result)

    return _run


def _parse(result):
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    rows = {}
    for line in filter(None, result.stdout.splitlines()):
        name, discogs_id, count = line.split("|")
        rows[name] = (discogs_id.strip(), int(count))
    return rows


@pytest.fixture
def album(tmp_path):
    """An album directory in pending/, as rsync would have left it."""

    def _make(name, discogs_id=30257615, flacs=2):
        d = tmp_path / name
        d.mkdir()
        for i in range(1, flacs + 1):
            (d / f"{i}.flac").write_bytes(b"")
        if discogs_id is not None:
            (d / "album.yaml").write_text(f"discogs_id: {discogs_id}\ncover_url: x\n")
        return d

    return _make


def test_an_empty_pending_directory_lists_nothing_instead_of_failing(listing, tmp_path):
    """The state dee is in once everything has been archived. `for d in */`
    made this a hard error, so reconcile crashed rather than saying nothing."""
    assert listing(tmp_path) == {}


def test_a_pending_directory_that_does_not_exist_is_not_an_error(listing, tmp_path):
    assert listing(tmp_path / "nope") == {}


@pytest.mark.parametrize(
    "name",
    [
        "Wax - No. 90009 (30257615)",  # every destination we generate ends in (id)
        "Daphni - Cherry (26241443)",
        "plain",
    ],
)
def test_album_names_with_spaces_and_parens_survive(listing, album, tmp_path, name):
    album(name, discogs_id=30257615, flacs=2)
    assert listing(tmp_path) == {name: ("30257615", 2)}


def test_reports_each_album_with_its_id_and_flac_count(listing, album, tmp_path):
    album("Wax - No. 90009 (30257615)", discogs_id=30257615, flacs=2)
    album("Daphni - Cherry (26241443)", discogs_id=26241443, flacs=16)
    assert listing(tmp_path) == {
        "Wax - No. 90009 (30257615)": ("30257615", 2),
        "Daphni - Cherry (26241443)": ("26241443", 16),
    }


def test_an_album_without_an_album_yaml_reports_no_id(listing, album, tmp_path):
    """These are the ones reconcile refuses to guess at."""
    album("mystery", discogs_id=None, flacs=3)
    assert listing(tmp_path) == {"mystery": ("", 3)}


def test_a_directory_holding_no_flacs_counts_zero(listing, album, tmp_path):
    """The same failed-glob bug, one level down: `ls "$d"/*.flac` in zsh."""
    album("empty", discogs_id=30257615, flacs=0)
    assert listing(tmp_path) == {"empty": ("30257615", 0)}


def test_loose_files_in_pending_are_not_mistaken_for_albums(listing, album, tmp_path):
    album("wax", discogs_id=30257615, flacs=1)
    (tmp_path / "notes.txt").write_text("hello")
    assert listing(tmp_path) == {"wax": ("30257615", 1)}
