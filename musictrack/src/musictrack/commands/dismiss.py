"""Stop reporting one row.

The id comes from the report's first column, so dismissing something is a
matter of copying what you are looking at.
"""

from __future__ import annotations

import typer

from musictrack.console import console
from musictrack.store import Dismissals


def split_row_id(row_id: str) -> tuple[str, str]:
    """`source:ref` as the report prints it.

    Split once only. A Spotify ref can itself contain colons.
    """
    source, _, ref = (row_id or "").partition(":")
    if not source or not ref:
        raise typer.BadParameter(f"expected source:ref, got {row_id!r}")
    return source, ref


def dismiss(
    row_id: str = typer.Argument(..., help="The id from the report's first column."),
    reason: str = typer.Option("", "--reason", help="Why, for when you reread it later."),
) -> None:
    """Hide one row from future reports."""
    source, ref = split_row_id(row_id)
    Dismissals().add(source, ref, reason)
    console.print(f"[green]dismissed[/] {source}:{ref}")
