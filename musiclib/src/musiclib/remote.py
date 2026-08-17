"""Talking to the music server: what we send, and how we ask it to run things."""

from __future__ import annotations

import shlex
import subprocess
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


def beet_import_command(destinations: list[str]) -> list[str]:
    """Hand off to beets on dee. -t because the import prompts."""
    quoted = " ".join(shlex.quote(d) for d in destinations)
    return [
        "ssh",
        "-t",
        "-o",
        "RemoteCommand=none",
        HOST,
        f"cd {shlex.quote(REMOTE_PENDING)} && beet import {quoted}",
    ]


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
