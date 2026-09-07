"""What you want against what you have.

Read-only. Every source is read live, the whole comparison happens in memory,
and nothing is written anywhere except the dismissals you record yourself.

The three tables are not equally confident. Owned rows are statements: an exact
title with an agreeing artist was right essentially every time across 338
matches. Absent rows are questions: `not found` was wrong nine times in ten,
because a shop and a tagger name the same record differently and every
difference reads as absence. The headings say so.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass, field

import typer
from rich.table import Table

from musictrack.config import load_bandcamp_cookie
from musictrack.console import console
from musictrack.errors import MissingToken, SourceError
from musictrack.match import ABSENT, OWNED, LibraryIndex, Match
from musictrack.models import AlbumRef
from musictrack.sources import library as beets
from musictrack.sources.bandcamp import BandcampClient
from musictrack.sources.spotify import spotify_client, to_listen
from musictrack.store import Dismissals

Row = tuple[AlbumRef, Match]


@dataclass
class Report:
    """Every candidate, sorted by how sure we are."""

    owned: list[Row] = field(default_factory=list)
    possible: list[Row] = field(default_factory=list)
    absent: list[Row] = field(default_factory=list)


def classify(
    candidates: Sequence[AlbumRef],
    library: LibraryIndex,
    hidden: dict[tuple[str, str], str],
) -> Report:
    """Look every candidate up, dropping the ones already judged."""
    report = Report()
    for candidate in candidates:
        if (candidate.source, candidate.ref) in hidden:
            continue
        match = library.look_up(candidate)
        if match.verdict == OWNED:
            report.owned.append((candidate, match))
        elif match.verdict == ABSENT:
            report.absent.append((candidate, match))
        else:
            report.possible.append((candidate, match))
    return report


Dismissed = dict[tuple[str, str], str]


def _table(
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


def wants_table(report: Report, dismissed: Dismissed | None = None) -> Table:
    return _table("wants you already have", report.owned, show_library=True, dismissed=dismissed)


def possible_table(report: Report, dismissed: Dismissed | None = None) -> Table:
    return _table(
        "worth a look: not a certain match, tier says why",
        report.possible,
        True,
        show_tier=True,
        dismissed=dismissed,
    )


def backlog_table(report: Report, dismissed: Dismissed | None = None) -> Table:
    return _table(
        "bought, not found in the library (check before importing)",
        report.absent,
        False,
        dismissed=dismissed,
    )


def reconcile(
    wants: bool = typer.Option(False, "--wants", help="Only the wants report."),
    backlog: bool = typer.Option(False, "--backlog", help="Only the backlog report."),
    include_dismissed: bool = typer.Option(
        False,
        "--include-dismissed",
        help="Show dismissed rows too, marked with their reason.",
    ),
) -> None:
    """Compare Bandcamp and Spotify against the beets library."""
    show_wants = wants or not backlog
    show_backlog = backlog or not wants

    try:
        dismissals = Dismissals().hidden()
        # Hiding and marking are opposites of the same lookup: the default run
        # filters candidates out before they are classified, --include-dismissed
        # classifies everything and marks the dismissed ones instead.
        hide = {} if include_dismissed else dismissals
        mark = dismissals if include_dismissed else None
        with console.status("reading the library"):
            index = LibraryIndex(albums=beets.album_refs(), tracks=beets.track_refs())
        bandcamp = BandcampClient(load_bandcamp_cookie())
        with console.status("reading Bandcamp"):
            wishlist = bandcamp.wishlist() if show_wants else []
            collection = bandcamp.collection() if show_backlog else []
        listening: list[AlbumRef] = []
        if show_wants:
            with console.status("reading Spotify"):
                listening = to_listen(spotify_client())
    except MissingToken as problem:
        console.print(f"[red]{problem}[/]")
        raise typer.Exit(1) from problem
    except SourceError as problem:
        console.print(f"[red]{problem}[/]")
        raise typer.Exit(1) from problem
    except (OSError, sqlite3.Error) as problem:
        console.print(f"[red]could not open the dismissals database: {problem}[/]")
        raise typer.Exit(1) from problem

    if show_wants:
        report = classify([*wishlist, *listening], index, hide)
        console.print(f"[dim]{len(wishlist) + len(listening)} wants read[/]")
        console.print(wants_table(report, mark))
        console.print(possible_table(report, mark))

    if show_backlog:
        report = classify(collection, index, hide)
        console.print(f"[dim]{len(collection)} purchases read[/]")
        console.print(backlog_table(report, mark))
        console.print(
            "[dim]a row here means no title matched, which is usually a naming "
            "difference rather than a missing record[/]"
        )
        console.print(f"[dim]{len(report.owned)} owned, {len(report.possible)} worth a look[/]")
