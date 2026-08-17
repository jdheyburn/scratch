import shlex
from pathlib import Path

from musiclib.remote import beet_import_command, rsync_command
from musiclib.tags import tags_for


def test_tags_carry_the_release_id_and_a_numerically_parsed_track_number():
    assert tags_for("10.flac", discogs_id=26241443) == {
        "MUSICBRAINZ_ALBUMID": "26241443",
        "TRACKNUMBER": "10",
    }


def test_an_album_without_a_release_still_gets_its_track_number():
    assert tags_for("3.flac", discogs_id=None) == {"TRACKNUMBER": "3"}


def test_rsync_disables_the_tmux_remote_command_so_the_transfer_can_run():
    cmd = rsync_command(Path("/src/daphni"), "Daphni - Cherry (26241443)")
    ssh_arg = cmd[cmd.index("-e") + 1]
    assert "RemoteCommand=none" in ssh_arg
    assert "RequestTTY=no" in ssh_arg


def test_rsync_sends_only_the_files_that_belong_on_the_server():
    cmd = rsync_command(Path("/src/daphni"), "dest")
    assert "--include=*.flac" in cmd
    assert "--include=album.yaml" in cmd
    assert "--include=cover.jpg" in cmd
    assert "--exclude=*" in cmd
    # 20 GB of Audacity projects must never leave the Mac.
    assert not any("aup3" in part for part in cmd)


def test_rsync_does_not_compress_already_compressed_audio():
    assert "-z" not in rsync_command(Path("/src/daphni"), "dest")


def test_the_remote_path_survives_the_remote_shell():
    """rsync expands the remote path in dee's shell, which is zsh — and every
    destination we generate ends in `(id)`, which zsh tries to glob."""
    cmd = rsync_command(Path("/src/wax"), "Wax - No. 90009 (30257615)")
    host, _, remote = cmd[-1].partition(":")

    assert host == "dee"
    # Quoted, so zsh sees a literal path rather than a glob pattern.
    assert remote == shlex.quote("/mnt/nfs/media/pending/vinyl/Wax - No. 90009 (30257615)/")
    assert shlex.split(remote) == ["/mnt/nfs/media/pending/vinyl/Wax - No. 90009 (30257615)/"]


def test_the_local_source_is_not_shell_quoted():
    """The source never touches a shell — we exec rsync directly — so quoting it
    would make the quotes part of the filename."""
    cmd = rsync_command(Path("/src/jump source"), "dest")
    assert cmd[-2] == "/src/jump source/"


def test_rsync_trailing_slashes_copy_contents_into_the_named_destination():
    cmd = rsync_command(Path("/src/daphni"), "Daphni - Cherry (26241443)")
    source, destination = cmd[-2], cmd[-1]
    assert source == "/src/daphni/"
    # Unquote as the remote shell will, then check where it actually lands.
    [remote] = shlex.split(destination.partition(":")[2])
    assert remote == "/mnt/nfs/media/pending/vinyl/Daphni - Cherry (26241443)/"


def test_the_import_command_quotes_directory_names_containing_spaces_and_parens():
    remote = beet_import_command(["Daphni - Cherry (26241443)", "Mammo (1)"])[-1]
    assert "'Daphni - Cherry (26241443)'" in remote
    assert "'Mammo (1)'" in remote


def test_the_import_command_asks_for_a_tty_because_beets_prompts():
    assert "-t" in beet_import_command(["x"])


def test_the_import_command_names_only_the_given_directories():
    """Never a bare `.` — importing an album this run didn't sync is a surprise."""
    remote = beet_import_command(["one", "two"])[-1]
    assert remote.endswith("beet import one two")


def test_tags_include_everything_that_distinguishes_one_pressing_from_another(make_release):
    """Album and artist alone can't separate a reissue from the release you
    asked for — they're identical. Year, catalogue, media and label can."""
    release = make_release(
        artists=[{"name": "Wax (4)"}],
        title="No. 90009",
        year=2024,
        labels=[{"name": "Wax", "catno": "WAX 90009"}],
        formats=[{"name": "Vinyl"}],
    )
    assert tags_for("1.flac", discogs_id=30257615, release=release) == {
        "TRACKNUMBER": "1",
        "MUSICBRAINZ_ALBUMID": "30257615",
        "ALBUM": "No. 90009",
        "ALBUMARTIST": "Wax",
        "DATE": "2024",
        "CATALOGNUMBER": "WAX 90009",
        "MEDIA": "Vinyl",
        "LABEL": "Wax",
    }


def test_missing_release_fields_are_simply_omitted(make_release):
    release = make_release(title="Untitled", year=None, labels=[], formats=[])
    tags = tags_for("1.flac", discogs_id=1, release=release)
    assert "DATE" not in tags
    assert "CATALOGNUMBER" not in tags
    assert tags["ALBUM"] == "Untitled"


def test_no_album_tags_when_there_is_no_release():
    assert tags_for("1.flac", discogs_id=None, release=None) == {"TRACKNUMBER": "1"}


def test_still_no_track_titles_because_a_mis_split_would_make_them_wrong(make_release):
    tags = tags_for("1.flac", discogs_id=1, release=make_release())
    assert "TITLE" not in tags
    assert "ARTIST" not in tags
