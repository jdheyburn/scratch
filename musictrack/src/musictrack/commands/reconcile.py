"""What you want against what you have.

Read-only against Bandcamp and beets: nothing changes on either. Raindrop
bookmarks and Spotify playlist entries can both be deleted from the walk
below, since both have a real API to do it, and Bandcamp does not. Reports
are served from a local copy of each source, whose age is printed on every
run, and refreshed on demand with `--refresh`.

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
from datetime import UTC, datetime

import typer

from musictrack.cache import SourceCache
from musictrack.commands.reconcile_views import (
    BACKLOG_TITLE,
    POSSIBLE_TITLE,
    WANTS_TITLE,
    Row,
    backlog_table,
    possible_table,
    wants_table,
)
from musictrack.commands.reconcile_walk import (
    LazyRaindropClient,
    LazySpotifyClient,
    raindrop_deleter,
    spotify_deleter,
    walk,
)
from musictrack.console import console
from musictrack.errors import MissingToken, RaindropError, SourceError
from musictrack.gather import Fetchers, UnknownSource, age_line, gather, keys_for, source_ages
from musictrack.match import ABSENT, OWNED, LibraryIndex
from musictrack.models import AlbumRef
from musictrack.store import DB_PATH, Dismissals


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


def reconcile(
    wants: bool = typer.Option(False, "--wants", help="Only the wants report."),
    backlog: bool = typer.Option(False, "--backlog", help="Only the backlog report."),
    include_dismissed: bool = typer.Option(
        False,
        "--include-dismissed",
        help="Show dismissed rows too, marked with their reason.",
    ),
    refresh: str | None = typer.Option(
        None,
        "--refresh",
        metavar="SOURCE",
        help="Refetch before reporting: all, beets, bandcamp, spotify, or raindrop.",
    ),
) -> None:
    """Compare the Bandcamp wishlist, Spotify "To Listen", and Raindrop
    bookmarks against the beets library."""
    show_wants = wants or not backlog
    show_backlog = backlog or not wants

    try:
        store = Dismissals()
        dismissed = store.hidden()
        # Hiding and marking are opposites of the same lookup: the default run
        # filters candidates out before they are classified, --include-dismissed
        # classifies everything and marks the dismissed ones instead.
        hide = {} if include_dismissed else dismissed
        mark = dismissed if include_dismissed else None
        cache = SourceCache()
        keys = keys_for(show_wants, show_backlog)
        with console.status("gathering sources"):
            gathered = gather(cache, Fetchers().as_map(), keys, refresh)
        console.print(age_line(source_ages(cache, keys), datetime.now(UTC)))
    except UnknownSource as problem:
        console.print(f"[red]{problem}[/]")
        raise typer.Exit(1) from problem
    except MissingToken as problem:
        console.print(f"[red]{problem}[/]")
        raise typer.Exit(1) from problem
    except (RaindropError, SourceError) as problem:
        console.print(f"[red]{problem}[/]")
        raise typer.Exit(1) from problem
    except (OSError, sqlite3.Error) as problem:
        console.print(f"[red]could not open {DB_PATH}: {problem}[/]")
        raise typer.Exit(1) from problem

    index = LibraryIndex(albums=gathered.rows["beets"], tracks=gathered.rows["beets-track"])
    wishlist = gathered.rows.get("bandcamp-wishlist", [])
    collection = gathered.rows.get("bandcamp-collection", [])
    listening = gathered.rows.get("spotify", [])
    raindrop_wants = gathered.rows.get("raindrop", [])
    deleters = {
        "raindrop": raindrop_deleter(LazyRaindropClient()),
        "spotify": spotify_deleter(LazySpotifyClient()),
    }

    if show_wants:
        report = classify([*wishlist, *listening, *raindrop_wants], index, hide)
        console.print(f"[dim]{len(wishlist) + len(listening) + len(raindrop_wants)} wants read[/]")
        if include_dismissed:
            console.print(wants_table(report.owned, mark))
            console.print(possible_table(report.possible, mark))
        else:
            walk(store, deleters, WANTS_TITLE, report.owned, show_library=True)
            walk(
                store,
                deleters,
                POSSIBLE_TITLE,
                report.possible,
                show_library=True,
                show_tier=True,
            )

    if show_backlog:
        report = classify(collection, index, hide)
        console.print(f"[dim]{len(collection)} purchases read[/]")
        if include_dismissed:
            console.print(backlog_table(report.absent, mark))
        else:
            walk(store, deleters, BACKLOG_TITLE, report.absent, show_library=False)
        console.print(
            "[dim]a row here means no title matched, which is usually a naming "
            "difference rather than a missing record[/]"
        )
        console.print(f"[dim]{len(report.owned)} owned, {len(report.possible)} worth a look[/]")
