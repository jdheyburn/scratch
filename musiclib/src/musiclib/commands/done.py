"""`musiclib vinyl done` — verify against beets, then archive both sides."""

from __future__ import annotations

import shutil
from pathlib import Path

import typer
from rich.prompt import Confirm

from musiclib.albumfile import load_album
from musiclib.console import console
from musiclib.library import applied_album, gate_verdict, library_report
from musiclib.remote import REMOTE_ARCHIVE, REMOTE_PENDING, archive_command, run_remote
from musiclib.state import DONE_DIRNAME, VINYL_ROOT, all_states, timestamp, update_state


def done(
    slugs: list[str] = typer.Argument(None, help="Albums to archive; default is all imported."),
    root: Path = typer.Option(VINYL_ROOT),
    dry_run: bool = typer.Option(False),
) -> None:
    """Verify against beets, then archive both sides. Deletes nothing."""
    states = {s: st for s, st in all_states(root).items() if not st.get("archived_at")}
    if slugs:
        states = {s: st for s, st in states.items() if s in slugs}

    for slug, state in states.items():
        doc_path = root / slug / "album.yaml"
        discogs_id = load_album(doc_path).get("discogs_id") if doc_path.is_file() else None
        dest, expected = state.get("dest"), state.get("flac_count")
        discogs_id = state.get("applied_albumid") or discogs_id
        if not dest:
            continue

        console.print(f"[b]{slug}[/] → {dest}")
        if discogs_id is None:
            console.print("  [yellow]no release id — verify by hand[/]")
            continue

        # The gate: album present, item count matching, every file on disk.
        albums, files = library_report(int(discogs_id))
        reason = gate_verdict(albums, files, expected)

        if reason is not None:
            # You can pick a different pressing at the beets prompt than the
            # one you captured, so the applied id won't always match. Offer
            # what we found; never assume it.
            applied = applied_album(doc_path, expected)
            if applied is None:
                console.print(f"  [red]{reason}[/]")
                continue
            console.print(f"  [yellow]in the library under {applied.albumid}, not {discogs_id}[/]")
            console.print(f"    {applied.artist} - {applied.album}, {applied.items} items")
            if dry_run:
                console.print("  [dim]would ask you to confirm, then archive[/]")
                continue
            if not Confirm.ask("    Same record?", default=False):
                continue
            update_state(root, slug, applied_albumid=applied.albumid)
            albums, files = library_report(int(applied.albumid))
            if (reason := gate_verdict(albums, files, expected)) is not None:
                console.print(f"  [red]{reason}[/]")
                continue

        console.print(f"  [green]verified[/] {albums} album, {len(files)} files")
        if dry_run:
            console.print(f"  [dim]would archive[/] {REMOTE_PENDING}/{dest} → {REMOTE_ARCHIVE}")
            continue
        run_remote(archive_command(dest))
        (root / DONE_DIRNAME).mkdir(exist_ok=True)
        shutil.move(str(root / slug), str(root / DONE_DIRNAME / slug))
        update_state(root, slug, archived_at=timestamp())
        console.print("  archived")
