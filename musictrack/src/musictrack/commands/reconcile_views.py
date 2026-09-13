"""The tables `reconcile` shows, whether walking them or printing them whole."""

from __future__ import annotations

from rich.table import Table

from musictrack.match import Match
from musictrack.models import AlbumRef

Row = tuple[AlbumRef, Match]
Dismissed = dict[tuple[str, str], str]

WANTS_TITLE = "wants you already have"
POSSIBLE_TITLE = "worth a look: not a certain match, tier says why"
BACKLOG_TITLE = "bought, not found in the library (check before importing)"


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
        cells = [f"{candidate.source}:{candidate.ref}", candidate.artist, candidate.album]
        if show_library:
            found = match.library
            cells.append(f"{found.artist} / {found.album}" if found else "")
        if show_tier:
            cells.append(match.tier)
        if dismissed is not None:
            key = (candidate.source, candidate.ref)
            if key in dismissed:
                reason = dismissed[key]
                cells.append(f"dismissed: {reason}" if reason else "dismissed")
            else:
                cells.append("")
        table.add_row(*cells)
    return table


def wants_table(rows: list[Row], dismissed: Dismissed | None = None) -> Table:
    return row_table(WANTS_TITLE, rows, show_library=True, dismissed=dismissed)


def possible_table(rows: list[Row], dismissed: Dismissed | None = None) -> Table:
    return row_table(POSSIBLE_TITLE, rows, True, show_tier=True, dismissed=dismissed)


def backlog_table(rows: list[Row], dismissed: Dismissed | None = None) -> Table:
    return row_table(BACKLOG_TITLE, rows, False, dismissed=dismissed)
