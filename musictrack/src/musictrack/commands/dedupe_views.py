"""What the dedupe command shows before it asks for a decision."""

from __future__ import annotations

from rich.table import Table

from musictrack.models import Raindrop
from musictrack.plan import Group, Plan
from musictrack.raindrop_identity import parse_release
from musictrack.raindrop_links import entry_link, shop_link


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
    return f"{shop_link(raindrop)}\n[dim]{parsed[0]} — {parsed[1]}[/]"


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
    table.add_column("raindrop")
    table.add_column("remove", overflow="fold")
    table.add_column("raindrop")
    table.add_column("matched as")
    for group, matched_as in rows:
        artist, album = matched_as
        table.add_row(
            _member_cell(group.survivor, matched_as),
            entry_link(group.survivor),
            "\n\n".join(_member_cell(extra, matched_as) for extra in group.extras),
            "\n\n".join(entry_link(extra) for extra in group.extras),
            f"{artist} — {album}",
        )
    return table


def group_panel(group: Group) -> Table:
    """What a group looks like before it's decided: what survives, what
    doesn't, and why the tool thinks they're the same release."""
    title = (
        f"fuzzy match: {group.matched_as[0]} — {group.matched_as[1]}"
        if group.matched_as is not None
        else "exact URL match"
    )
    table = Table(title=title)
    table.add_column("keep")
    table.add_column("raindrop")
    table.add_column("remove")
    table.add_column("raindrop")
    table.add_row(
        shop_link(group.survivor),
        entry_link(group.survivor),
        "\n".join(shop_link(extra) for extra in group.extras),
        "\n".join(entry_link(extra) for extra in group.extras),
    )
    return table
