"""The command-line surface.

Commands are registered here rather than by decorator inside each module, so
the wiring is in one readable place and the command modules stay importable on
their own.
"""

from __future__ import annotations

import typer

from musictrack import __version__
from musictrack.commands import dedupe, dismiss, reconcile

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Keeps the places new music is tracked in agreement with each other.",
)


def _print_version(value: bool) -> None:
    # Runs as the option is parsed, before Click checks that a subcommand was
    # given. A check inside the callback body would run too late.
    if value:
        typer.echo(f"musictrack {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_print_version,
        is_eager=True,
        help="Print the version and exit.",
    ),
) -> None:
    pass


raindrop = typer.Typer(no_args_is_help=True, help="Raindrop.io bookmarks.")
app.add_typer(raindrop, name="raindrop")

raindrop.command()(dedupe.dedupe)
app.command()(reconcile.reconcile)
app.command()(dismiss.dismiss)


def main() -> None:
    app()
