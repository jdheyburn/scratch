"""The command-line surface.

Commands are registered here rather than by decorator inside each module, so
the wiring is in one readable place and the command modules stay importable on
their own.
"""

from __future__ import annotations

import typer

from musictrack.commands import dedupe, dismiss, reconcile

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Keeps the places new music is tracked in agreement with each other.",
)
raindrop = typer.Typer(no_args_is_help=True, help="Raindrop.io bookmarks.")
app.add_typer(raindrop, name="raindrop")

raindrop.command()(dedupe.dedupe)
app.command()(reconcile.reconcile)
app.command()(dismiss.dismiss)


def main() -> None:
    app()
