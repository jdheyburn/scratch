"""`musiclib vinyl reconcile` — catch up with albums imported outside a sync run."""

from __future__ import annotations

import typer

from musiclib.console import console
from musiclib.library import album_count
from musiclib.remote import archive_command, pending_listing_command, run_remote


def reconcile(dry_run: bool = typer.Option(False)) -> None:
    """Archive pending directories already in the library; list the rest."""
    listing = run_remote(pending_listing_command())

    unidentified = []
    for line in filter(None, listing.splitlines()):
        name, discogs_id, count = line.split("|")
        if not discogs_id.strip() or discogs_id.strip() == "null":
            unidentified.append((name, count))
            continue
        if not album_count(discogs_id.strip()):
            console.print(f"  [yellow]{name}[/] — has an id but isn't in the library")
            continue
        console.print(f"  [green]{name}[/] — imported")
        if not dry_run:
            run_remote(archive_command(name))

    if unidentified:
        console.print("\n[b]Unidentified — not touched:[/]")
        for name, count in unidentified:
            console.print(f"  {name}  ({count.strip()} flacs)")
