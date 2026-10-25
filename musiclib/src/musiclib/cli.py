"""The command-line surface.

Commands are registered here rather than by decorator inside each module, so
the wiring is in one readable place and the command modules stay importable on
their own.
"""

from __future__ import annotations

import typer

from musiclib import __version__
from musiclib.commands import done, gc, reconcile, sync

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Music library tooling.")


def _print_version(value: bool) -> None:
    # Runs as the option is parsed, before Click checks that a subcommand was
    # given. A check inside the callback body would run too late.
    if value:
        typer.echo(f"musiclib {__version__}")
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


vinyl = typer.Typer(no_args_is_help=True, help="Digitised vinyl: sync, verify, archive.")
app.add_typer(vinyl, name="vinyl")

vinyl.command()(sync.sync)
vinyl.command()(done.done)
vinyl.command()(gc.gc)
vinyl.command()(reconcile.reconcile)


def main() -> None:
    app()
