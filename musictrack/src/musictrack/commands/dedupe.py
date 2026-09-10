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
from musictrack.models import Raindrop
from musictrack.plan import MUSIC_COLLECTION, Group, Plan, build_plan
from musictrack.raindrop import RaindropClient
from musictrack.raindrop_identity import parse_release


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


def _member_cell(raindrop: Raindrop, fallback: tuple[str, str]) -> str:
    """A raindrop's link next to what its own title actually parsed to.

    Falls back to the group's shared `matched_as` only if re-parsing this
    member somehow fails, which shouldn't happen for anything `group_by_release`
    already accepted — but a display fallback is safer than a crash."""
    parsed = parse_release(raindrop) or fallback
    return f"{raindrop.link}\n[dim]{parsed[0]} — {parsed[1]}[/]"


def fuzzy_preview(plan: Plan) -> Table | None:
    """One row per fuzzy-matched group, showing why it was proposed. `None`
    when the plan has no fuzzy groups — printed only when there is something
    worth a second look, since a shared loose title and an agreeing artist is
    weaker evidence than a shared URL.

    Each raindrop's own parsed (artist, album) is shown next to its link, not
    just the seed's — so a human can see what every member actually said,
    rather than trusting one shared label."""
    rows: list[tuple[Group, tuple[str, str]]] = []
    for group in plan.groups:
        if group.matched_as is None:
            continue
        rows.append((group, group.matched_as))
    if not rows:
        return None
    table = Table(title="worth a look before confirming: matched by title, not URL")
    table.add_column("keep", overflow="fold")
    table.add_column("remove", overflow="fold")
    table.add_column("matched as")
    for group, matched_as in rows:
        artist, album = matched_as
        table.add_row(
            _member_cell(group.survivor, matched_as),
            "\n\n".join(_member_cell(extra, matched_as) for extra in group.extras),
            f"{artist} — {album}",
        )
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

    preview = fuzzy_preview(plan)
    if preview is not None:
        console.print(preview)

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
