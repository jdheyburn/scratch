"""Reading beets. The runner is injected, so no test opens an SSH connection."""

import pytest

from musictrack.errors import LibraryError
from musictrack.sources.library import album_refs, track_refs


class _Runner:
    """A recording double for the injected runner. Matches the class-based
    spy convention already used in test_client.py, rather than bolting an
    attribute onto a bare function."""

    def __init__(self, output):
        self.output = output
        self.script = ""

    def __call__(self, script):
        self.script = script
        return self.output


def runner(output):
    return _Runner(output)


def test_albums_are_parsed_into_refs():
    run = runner("Theo Parrish@@Parallel Dimensions\nzakè@@Lapis\n")
    refs = album_refs(run)
    assert [(r.artist, r.album) for r in refs] == [
        ("Theo Parrish", "Parallel Dimensions"),
        ("zakè", "Lapis"),
    ]
    assert all(r.source == "beets" for r in refs)


def test_a_title_containing_a_pipe_survives():
    """The library holds 'Two Hands | One Engine'. A pipe delimiter would split
    that row in the wrong place and silently invent an album."""
    refs = album_refs(runner("Two Hands | One Engine@@Hecla\n"))
    assert [(r.artist, r.album) for r in refs] == [("Two Hands | One Engine", "Hecla")]


def test_a_singleton_track_with_no_album_still_becomes_a_ref():
    """21 of 27 Bandcamp track purchases are singletons with an empty album."""
    refs = track_refs(runner("Zorrovian@@BIOS@@@@Zorrovian\n"))
    assert [(r.artist, r.album) for r in refs] == [("Zorrovian", "BIOS")]
    assert refs[0].source == "beets-track"


def test_blank_and_malformed_lines_are_skipped():
    refs = album_refs(runner("\nArtist@@Album\ngarbage-with-no-delimiter\n"))
    assert len(refs) == 1


def test_the_album_query_asks_beets_for_albums_not_tracks():
    run = runner("")
    album_refs(run)
    assert "beet ls -a" in run.script
    assert "$albumartist@@$album" in run.script


def test_a_failing_runner_becomes_a_libraryerror():
    def boom(script):
        raise OSError("ssh: connect: host is down")

    with pytest.raises(LibraryError):
        album_refs(boom)
