"""Reading Plex. The runner is injected, so no test opens an SSH connection."""

import pytest

import musictrack.sources.plex as plex_module
from musictrack.errors import MissingToken, PlexError
from musictrack.sources.plex import MUSIC_ROOT, album_refs, link, track_refs

MACHINE = "0000feed"
SERVER = "https://plex.example"
LINK_42 = (
    "https://plex.example/web/index.html#!/server/0000feed/details?key=%2Flibrary%2Fmetadata%2F42"
)


@pytest.fixture(autouse=True)
def server_url(monkeypatch):
    """The server's own address is per-account config, never in the repo."""
    monkeypatch.setattr(plex_module, "load_plex_url", lambda: SERVER)


class _Runner:
    """A recording double for the injected runner."""

    def __init__(self, output):
        self.output = output
        self.script = ""

    def __call__(self, script):
        self.script = script
        return self.output


def dump(*lines):
    return _Runner("\n".join([f"machine@@{MACHINE}", *lines]) + "\n")


def test_the_link_opens_the_album_in_the_servers_own_web_app():
    assert link(SERVER, MACHINE, "42") == LINK_42


def test_a_trailing_slash_on_the_server_url_is_not_doubled():
    assert link(SERVER + "/", MACHINE, "42") == LINK_42


def test_no_server_url_is_a_plexerror_that_says_how_to_set_one(monkeypatch):
    def missing():
        raise MissingToken("No Plex server URL at ~/.config/plex/url.")

    monkeypatch.setattr(plex_module, "load_plex_url", missing)
    with pytest.raises(PlexError, match="config/plex/url"):
        album_refs(dump("Theo Parrish@@Parallel Dimensions@@42"))


def test_albums_are_parsed_into_refs_that_link_to_themselves():
    refs = album_refs(dump("Theo Parrish@@Parallel Dimensions@@42"))
    assert [(r.source, r.artist, r.album, r.ref, r.url) for r in refs] == [
        ("plex-album", "Theo Parrish", "Parallel Dimensions", "42", LINK_42)
    ]


def test_tracks_are_parsed_into_refs_that_link_to_their_album():
    refs = track_refs(dump("Huerco S.@@[untitled]@@42"))
    assert [(r.source, r.artist, r.album, r.ref, r.url) for r in refs] == [
        ("plex-track", "Huerco S.", "[untitled]", "42", LINK_42)
    ]


def test_blank_and_malformed_lines_are_skipped():
    refs = album_refs(dump("", "garbage", "A@@B@@C@@D", "Artist@@Album@@7"))
    assert [r.album for r in refs] == ["Album"]


def test_a_dump_that_never_names_its_server_is_an_error():
    """Without the machine id there is no link to build, so every row would
    be useless. Say so rather than caching rows with broken links."""
    with pytest.raises(PlexError):
        album_refs(_Runner("Artist@@Album@@7\n"))


def test_a_failing_runner_becomes_a_plexerror():
    def boom(script):
        raise OSError("ssh: connect: host is down")

    with pytest.raises(PlexError):
        track_refs(boom)


def test_the_database_is_opened_read_only_and_only_the_music_section_is_read():
    run = dump()
    album_refs(run)
    assert "mode=ro" in run.script
    assert MUSIC_ROOT in run.script
    assert "metadata_type = 9" in run.script


def test_the_track_query_prefers_the_track_artist():
    """2867 of the Music section's 15520 tracks credit an artist other than the
    album artist. A featured artist must still find their track."""
    run = dump()
    track_refs(run)
    assert "original_title" in run.script
    assert "metadata_type = 10" in run.script


def test_a_null_column_is_never_printed_as_the_word_none():
    """`str(None)` is the literal string "None", which would look like a real
    title. The remote program must guard against that instead."""
    run = dump()
    album_refs(run)
    assert "join(str(part) for part in row)" not in run.script
    assert "is None else str(part)" in run.script


def test_the_generated_remote_program_is_valid_python():
    run = dump()
    album_refs(run)
    script = run.script
    program = script.split("<<'PY'\n", 1)[1].rsplit("\nPY\n", 1)[0]
    compile(program, "<plex-remote-script>", "exec")
