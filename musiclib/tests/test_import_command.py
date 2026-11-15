"""The shell snippet `sync` hands to beets on the music server.

Run under a real shell with a stand-in `beet`, for the same reason as the
pending listing: dee's login shell is zsh, and the destinations carry spaces
and parens. What matters is which `beet import` calls actually happen.
"""

import os
import shutil
import subprocess

import pytest

from musiclib.remote import beet_import_command

SHELLS = [s for s in ("zsh", "bash", "sh") if shutil.which(s)]

pytestmark = pytest.mark.skipif(not SHELLS, reason="needs a shell to run the snippet in")

# Records where it ran and its arguments, tab-separated, one call per line.
FAKE_BEET = """#!/bin/sh
{ printf '%s' "$PWD"; for a in "$@"; do printf '\\t%s' "$a"; done; echo; } >> "$BEET_LOG"
exit "${BEET_EXIT:-0}"
"""


@pytest.fixture(params=SHELLS)
def shell(request):
    return request.param


@pytest.fixture
def pending(tmp_path):
    d = tmp_path / "pending"
    d.mkdir()
    return d


@pytest.fixture
def beet_calls(shell, tmp_path, pending):
    """Run the import snippet against a fake `beet`; return its calls in order."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    beet = bin_dir / "beet"
    beet.write_text(FAKE_BEET)
    beet.chmod(0o755)
    log = tmp_path / "beet.log"

    def _run(albums, exit_code=0):
        script = beet_import_command(albums, directory=str(pending))[-1]
        env = {
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "BEET_LOG": str(log),
            "BEET_EXIT": str(exit_code),
        }
        subprocess.run([shell, "-c", script], env=env, capture_output=True, text=True)
        if not log.exists():
            return []
        return [line.split("\t") for line in log.read_text().splitlines()]

    return _run


def test_each_album_is_imported_by_its_own_release_id(beet_calls, pending):
    """beets then looks up only the captured release, so the Discogs plugin's
    int-vs-string id comparison can't push it down the candidate list."""
    calls = beet_calls(
        [
            ("Eden Aurelius - Entre Nous (38516943)", 38516943),
            ("Pridi - Apricity (38024289)", 38024289),
        ]
    )
    assert calls == [
        [
            str(pending),
            "import",
            "--search-id",
            "38516943",
            "Eden Aurelius - Entre Nous (38516943)",
        ],
        [str(pending), "import", "--search-id", "38024289", "Pridi - Apricity (38024289)"],
    ]


def test_an_album_without_a_release_id_gets_a_plain_import(beet_calls, pending):
    assert beet_calls([("Mammo (1)", None)]) == [[str(pending), "import", "Mammo (1)"]]


def test_a_failed_import_does_not_stop_the_albums_after_it(beet_calls):
    calls = beet_calls([("one", 1), ("two", 2)], exit_code=1)
    assert [c[-1] for c in calls] == ["one", "two"]
