"""`musiclib vinyl sync` — capture, check, tag, transfer, hand off to beets."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import typer
from rich.prompt import Confirm, Prompt
from rich.table import Table

from musiclib.albumfile import load_album, release_from_doc
from musiclib.capture import capture, refresh_album
from musiclib.console import console, run
from musiclib.discogs import discogs_token
from musiclib.library import applied_album, gate_verdict, library_report
from musiclib.preflight import destination_name, is_blocked, observe, preflight
from musiclib.remote import HOST, beet_import_command, rsync_command
from musiclib.state import (
    DONE_DIRNAME,
    RETENTION_DAYS,
    VINYL_ROOT,
    expired_albums,
    find_albums,
    read_state,
    timestamp,
    update_state,
)
from musiclib.tags import tag_album


def sync(
    slugs: list[str] = typer.Argument(None, help="Album directories; default is all pending."),
    root: Path = typer.Option(VINYL_ROOT, help="Where your rips live."),
    import_all: bool = typer.Option(False, help="Import all of pending/, not just this run."),
    recapture: bool = typer.Option(False, help="Re-prompt for release and cover."),
    refresh: bool = typer.Option(False, help="Re-fetch from an edited album.yaml."),
    dry_run: bool = typer.Option(False, help="Show what would happen, change nothing."),
) -> None:
    """Capture, check, tag, transfer, then hand off to beets."""
    _gc_reminder(root)

    directories = [d for d in find_albums(root) if not slugs or d.name in slugs]
    if not (recapture or refresh):
        directories = [d for d in directories if not read_state(root, d.name).get("imported_at")]
    if not directories:
        console.print("Nothing to sync.")
        raise typer.Exit()

    token = discogs_token()

    # Pass one: capture. Nothing is tagged or transferred yet.
    console.print(f"[b]Capture[/] — {len(directories)} album(s)\n")
    plan = []
    for d in directories:
        doc_path = d / "album.yaml"
        if refresh and doc_path.is_file():
            console.print(f"[b]{d.name}[/] — refreshing from album.yaml")
            refresh_album(d, token=token)
        if recapture:
            doc_path.unlink(missing_ok=True)
        if not doc_path.is_file():
            console.print(f"[b]{d.name}[/]")
            if not capture(d, token=token, ask=Prompt.ask, confirm=Confirm.ask, echo=console.print):
                console.print("  [dim]abandoned[/]\n")
                continue
            console.print()
        doc = load_album(doc_path)
        candidate = observe(d, release_from_doc(doc))
        plan.append((d, doc, candidate, preflight(candidate)))

    ready = [p for p in plan if not is_blocked(p[3])]
    blocked = [p for p in plan if is_blocked(p[3])]
    console.print(_preflight_table(plan))

    if blocked:
        console.print(f"\n[red]{len(blocked)} album(s) excluded.[/] Fix and re-run.")
    if not ready:
        raise typer.Exit(1)
    if not dry_run and not Confirm.ask(f"\nTag and transfer {len(ready)} album(s)?"):
        raise typer.Exit()

    # Pass two: execute.
    destinations = []
    for d, doc, candidate, _ in ready:
        discogs_id = doc.get("discogs_id")
        dest = destination_name(candidate.release, discogs_id, d.name)
        console.print(f"\n[b]{d.name}[/] → {dest}")

        if not dry_run:
            tagged = tag_album(d, discogs_id, candidate.release)
            console.print(f"  tagged {tagged} track(s)")
            update_state(root, d.name, dest=dest, flac_count=tagged, tagged_at=timestamp())

        if run(rsync_command(d, dest), dry_run) != 0:
            console.print("  [red]transfer failed; skipping[/]")
            continue
        if not dry_run:
            update_state(root, d.name, synced_at=timestamp())
        destinations.append(dest)

    if not destinations:
        raise typer.Exit(1)

    console.print(f"\n[b]Import[/] — {len(destinations)} album(s) on {HOST}\n")
    run(beet_import_command(["."] if import_all else destinations), dry_run)
    if not dry_run:
        _record_imports(root, ready)
        console.print("\nWhen you're happy with the matches: [b]musiclib vinyl done[/]")


def _preflight_table(plan: list) -> Table:
    table = Table(title="Pre-flight", title_justify="left", header_style="bold")
    table.add_column("album")
    table.add_column("tracks", justify="right")
    table.add_column("destination")
    table.add_column("notes")
    for d, doc, candidate, findings in plan:
        notes = "\n".join(
            f"[red]{f.message}[/]" if f.severity == "stop" else f"[yellow]{f.message}[/]"
            for f in findings
        )
        table.add_row(
            d.name,
            str(candidate.flac_count),
            destination_name(candidate.release, doc.get("discogs_id"), d.name),
            notes or "[green]ok[/]",
        )
    return table


def _gc_reminder(root: Path) -> None:
    expired = expired_albums(root, now=datetime.now().astimezone())
    if not expired:
        return
    total = 0
    for slug, _ in expired:
        d = root / DONE_DIRNAME / slug
        if d.is_dir():
            total += sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
    console.print(
        f"[yellow]{len(expired)} album(s) in done/ are older than {RETENTION_DAYS} days "
        f"({total / 1e9:.1f} GB). Run [b]musiclib vinyl gc[/b] to reclaim.[/]\n"
    )


def _record_imports(root: Path, ready: list) -> None:
    """Stamp imported_at only where beets actually took the album.

    Anything you skipped at the prompt stays un-imported, so the next sync
    offers it again instead of silently considering it finished.
    """
    for d, doc, _candidate, _ in ready:
        state = read_state(root, d.name)
        if not state.get("synced_at"):
            continue
        discogs_id = doc.get("discogs_id")
        if discogs_id is None:
            console.print(f"  [yellow]{d.name}: no release id — confirm by hand[/]")
            continue
        expected = state.get("flac_count")
        albums, files = library_report(int(discogs_id))
        if gate_verdict(albums, files, expected) is None:
            update_state(root, d.name, imported_at=timestamp())
            continue
        # Maybe you applied a different pressing than the one you captured.
        applied = applied_album(d / "album.yaml", expected)
        if applied is not None:
            console.print(
                f"  [yellow]{d.name}: imported under {applied.albumid}, not {discogs_id}[/]"
            )
            update_state(root, d.name, imported_at=timestamp(), applied_albumid=applied.albumid)
        else:
            console.print(f"  [yellow]{d.name}: not imported — will be offered again[/]")
