"""How `reconcile` shows a row: `row_table` for the bulk `--include-dismissed`
report, `row_listing` for one row at a time in the walk, beets-import style."""

from __future__ import annotations

from rich.markup import escape
from rich.table import Table
from rich.text import Text

from musictrack.match import Match
from musictrack.models import AlbumRef

Row = tuple[AlbumRef, Match]
Dismissed = dict[tuple[str, str], str]

WANTS_TITLE = "wants you already have"
POSSIBLE_TITLE = "worth a look: not a certain match, tier says why"
BACKLOG_TITLE = "bought, not found in the library (check before importing)"


def track_note(found: AlbumRef) -> str:
    """Where a track hit lives, so it can be found and checked: a track title
    alone ("[untitled]") says nothing about which record holds it. Empty for
    an album hit."""
    if found.source != "beets-track":
        return ""
    if found.appears_on:
        return f"a track on: {found.appears_on}"
    return "a singleton track, on no album"


def row_table(
    title: str,
    rows: list[Row],
    show_library: bool,
    show_tier: bool = False,
    dismissed: Dismissed | None = None,
) -> Table:
    table = Table(title=title)
    table.add_column("id", style="dim")
    table.add_column("artist")
    table.add_column("release")
    if show_library:
        table.add_column("in the library as")
    if show_tier:
        table.add_column("tier")
    if dismissed is not None:
        table.add_column("dismissed")
    for candidate, match in rows:
        # A title can contain literal brackets ("[untitled]", "Song [Remix]"),
        # which Rich would otherwise try to parse as markup tags and silently
        # swallow. Text() renders a cell's content literally, never as markup.
        cells = [
            Text(f"{candidate.source}:{candidate.ref}"),
            Text(candidate.artist),
            Text(candidate.album),
        ]
        if show_library:
            found = match.library
            label = f"{found.artist} / {found.album}" if found else ""
            note = track_note(found) if found else ""
            cells.append(Text(f"{label} ({note})" if note else label))
        if show_tier:
            cells.append(Text(match.tier))
        if dismissed is not None:
            key = (candidate.source, candidate.ref)
            if key in dismissed:
                reason = dismissed[key]
                cells.append(Text(f"dismissed: {reason}" if reason else "dismissed"))
            else:
                cells.append(Text(""))
        table.add_row(*cells)
    return table


def row_listing(
    candidate: AlbumRef, match: Match, show_library: bool, show_tier: bool = False
) -> str:
    """One row, beets-import style: a plain `Artist - Album` line with a few
    indented details underneath, rather than a bordered single-row table.

    Every piece of source text is escaped before it goes anywhere near the
    markup this builds — a title can contain literal brackets
    ("[untitled]", "Song [Remix]"), which Rich would otherwise try to parse
    as a style tag and silently swallow rather than print."""
    lines = [f"[bold]{escape(candidate.artist)} - {escape(candidate.album)}[/bold]"]
    if show_library and match.library is not None:
        found = match.library
        lines.append(f"  in the library as: {escape(found.artist)} / {escape(found.album)}")
        note = track_note(found)
        if note:
            lines.append(f"    {escape(note)}")
    if show_tier:
        lines.append(f"  tier: {escape(match.tier)}")
    if candidate.url:
        safe_url = escape(candidate.url)
        lines.append(f"  link: [link={safe_url}]{safe_url}[/link]")
    lines.append(f"  [dim]id: {escape(candidate.source)}:{escape(candidate.ref)}[/dim]")
    return "\n".join(lines)


def wants_table(rows: list[Row], dismissed: Dismissed | None = None) -> Table:
    return row_table(WANTS_TITLE, rows, show_library=True, dismissed=dismissed)


def possible_table(rows: list[Row], dismissed: Dismissed | None = None) -> Table:
    return row_table(POSSIBLE_TITLE, rows, True, show_tier=True, dismissed=dismissed)


def backlog_table(rows: list[Row], dismissed: Dismissed | None = None) -> Table:
    return row_table(BACKLOG_TITLE, rows, False, dismissed=dismissed)
