"""Remove duplicate music bookmarks, then file what's left.

One read-only pass builds the whole plan, which is shown as a table before
anything is written. Deduping and filing are confirmed separately, so you can
take one and decline the other.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

import typer
from rich.table import Table

from musictrack.config import load_token
from musictrack.console import console
from musictrack.errors import MissingToken, RaindropError
from musictrack.plan import MUSIC_COLLECTION, Plan, build_plan
from musictrack.raindrop import RaindropClient


class WriteClient(Protocol):
    """What apply_dedupe and apply_filing need from a client.

    Structural rather than `RaindropClient` itself, so a test double that
    merely walks like one — no network, no token — satisfies it too.
    """

    def set_tags(self, raindrop_id: int, tags: Sequence[str]) -> None: ...
    def move(self, ids: Sequence[int], collection_id: int) -> None: ...
    def delete(self, ids: Sequence[int]) -> None: ...


def summary(plan: Plan) -> Table:
    """One table, one glance: everything the run would change."""
    table = Table()
    table.add_column("action")
    table.add_column("count", justify="right")
    table.add_row("duplicate groups", str(len(plan.groups)))
    table.add_row("raindrops to delete", str(len(plan.deletions)))
    table.add_row("survivors gaining tags", str(len(plan.retags)))
    table.add_row("survivors to file", str(len(plan.survivor_moves)))
    table.add_row("stray links to file", str(len(plan.stray_moves)))
    return table


def apply_dedupe(client: WriteClient, plan: Plan) -> None:
    """Merge, move, then delete.

    The order is the safety property: an extra is only ever deleted after
    whatever it carried has been written onto the survivor, so a run that dies
    halfway loses nothing.
    """
    for raindrop_id, tags in plan.retags:
        client.set_tags(raindrop_id, tags)
    client.move(plan.survivor_moves, MUSIC_COLLECTION)
    client.delete(plan.deletions)


def apply_filing(client: WriteClient, plan: Plan) -> None:
    """Move the music links that aren't duplicates out of Unsorted."""
    client.move(plan.stray_moves, MUSIC_COLLECTION)


def dedupe(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show the plan, change nothing."),
) -> None:
    """Remove duplicate music bookmarks and file the strays."""
    try:
        client = RaindropClient(load_token())
    except MissingToken as problem:
        console.print(f"[red]{problem}[/]")
        raise typer.Exit(1) from problem

    with console.status("reading raindrops"):
        try:
            raindrops = client.all_raindrops()
        except RaindropError as problem:
            console.print(f"[red]{problem}[/]")
            raise typer.Exit(1) from problem

    plan = build_plan(raindrops)
    console.print(f"[dim]{len(raindrops)} raindrops read[/]")
    console.print(summary(plan))

    if plan.held_back_tags:
        # The date-tag format has changed once before. These carry a year but
        # match neither known shape, so they were kept off the survivors
        # rather than merged blind.
        console.print(
            "[yellow]held back, unrecognised date shape:[/] " + ", ".join(plan.held_back_tags)
        )

    if dry_run:
        console.print("[dim]dry run: nothing written[/]")
        return

    if plan.deletions or plan.retags or plan.survivor_moves:
        if typer.confirm(f"Delete {len(plan.deletions)} duplicate(s)?"):
            try:
                apply_dedupe(client, plan)
            except RaindropError as problem:
                console.print(f"[red]{problem}[/]")
                console.print(
                    "[red]tag merges and moves land before any deletion, so nothing "
                    "was lost; re-running is safe[/]"
                )
                raise typer.Exit(1) from problem
            console.print("[green]duplicates moved to Trash[/]")
        else:
            console.print("[dim]duplicates left alone[/]")

    if plan.stray_moves and typer.confirm(
        f"File {len(plan.stray_moves)} stray music link(s) into music?"
    ):
        try:
            apply_filing(client, plan)
        except RaindropError as problem:
            console.print(f"[red]{problem}[/]")
            console.print("[red]filing a stray twice is harmless; re-running is safe[/]")
            raise typer.Exit(1) from problem
        console.print("[green]strays filed[/]")
