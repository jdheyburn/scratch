"""Talking to the music server: what we send, and how we ask it to run things."""

from __future__ import annotations

import shlex
import subprocess
from collections.abc import Sequence
from pathlib import Path

from musiclib.errors import RemoteError

HOST = "dee"
REMOTE_PENDING = "/mnt/nfs/media/pending/vinyl"
REMOTE_ARCHIVE = "/mnt/nfs/media/vinyl-archive"

# `Host dee` sets RemoteCommand=tmux + RequestTTY, which makes ssh refuse to run
# a command at all. Override inline rather than depending on the -no-tmux alias.
SSH_OPTS = ["-o", "RemoteCommand=none", "-o", "RequestTTY=no"]


def rsync_command(source: Path, destination: str) -> list[str]:
    """Transfer one album. Trailing slashes put the contents inside `destination`."""
    return [
        "rsync",
        "-ahP",
        "--no-owner",
        "--no-group",
        "--no-perms",
        "-e",
        "ssh " + " ".join(SSH_OPTS),
        "--include=*/",
        "--include=*.flac",
        "--include=cover.jpg",
        "--include=album.yaml",
        "--exclude=*",
        f"{source}/",
        # rsync expands the remote path in dee's login shell (zsh), where the
        # `(id)` we append is a glob pattern. Quote it so zsh sees a literal
        # path. macOS ships openrsync, which has no --protect-args to do this
        # for us. The local source needs no quoting: we exec rsync directly.
        f"{HOST}:{shlex.quote(f'{REMOTE_PENDING}/{destination}/')}",
    ]


def beet_import_command(
    albums: Sequence[tuple[str, int | str | None]], directory: str = REMOTE_PENDING
) -> list[str]:
    """Hand off to beets on dee, one `beet import` per album. -t because the import prompts.

    Each album is searched by its own release id. Letting beets search instead
    loses the release you captured: the Discogs plugin returns its id as an int,
    beets compares it against the string in MUSICBRAINZ_ALBUMID, and the
    resulting id penalty lets Bandcamp and MusicBrainz copies outrank it.
    `;` rather than `&&`, so skipping or failing one album still imports the rest.
    """
    imports = "; ".join(
        "beet import "
        + (f"--search-id {shlex.quote(str(discogs_id))} " if discogs_id else "")
        + shlex.quote(destination)
        for destination, discogs_id in albums
    )
    return [
        "ssh",
        "-t",
        "-o",
        "RemoteCommand=none",
        HOST,
        f"cd {shlex.quote(directory)} && {imports}",
    ]


def pending_listing_command(directory: str = REMOTE_PENDING) -> str:
    """List what's sitting in pending/, one `name|discogs_id|flac_count` per line."""
    return (
        f"cd {shlex.quote(directory)} 2>/dev/null || exit 0;"
        # `for d in */` and `ls "$d"/*.flac` read naturally, but dee's login
        # shell is zsh, where a glob matching nothing is a hard error rather
        # than an empty loop — so an emptied pending/ crashed this command
        # instead of reporting nothing to do. find loops zero times, and
        # handles the spaces and parens every destination name carries.
        ' find . -mindepth 1 -maxdepth 1 -type d ! -name ".*" | sort |'
        ' while IFS= read -r d; do d="${d#./}";'
        ' id=$(sed -n "s/^discogs_id: *//p" "$d/album.yaml" 2>/dev/null);'
        ' n=$(find "$d" -maxdepth 1 -type f -name "*.flac" | wc -l | tr -d " ");'
        ' echo "$d|$id|$n"; done'
    )


def pending_albums(listing: str) -> list[tuple[str, str | None]]:
    """Parse `pending_listing_command` output into (destination, discogs_id) pairs."""
    albums: list[tuple[str, str | None]] = []
    for line in filter(None, listing.splitlines()):
        name, discogs_id, _ = line.split("|")
        discogs_id = discogs_id.strip()
        albums.append((name, discogs_id if discogs_id and discogs_id != "null" else None))
    return albums


def archive_command(destination: str) -> str:
    """Move one imported album out of pending/ and into the archive."""
    return (
        f"mkdir -p {shlex.quote(REMOTE_ARCHIVE)} &&"
        f" mv {shlex.quote(f'{REMOTE_PENDING}/{destination}')} {shlex.quote(REMOTE_ARCHIVE)}/"
    )


def run_remote(script: str) -> str:
    """Run a shell snippet on dee and return its stdout."""
    result = subprocess.run(
        ["ssh", *SSH_OPTS, HOST, script], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RemoteError(result.stderr.strip() or f"ssh failed ({result.returncode})")
    return result.stdout
