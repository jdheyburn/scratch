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


@app.callback()
def _root(
    version: bool = typer.Option(False, "--version", is_eager=True, help="Print the version and exit."),
) -> None:
    if version:
        typer.echo(f"musiclib {__version__}")
        raise typer.Exit()


vinyl = typer.Typer(no_args_is_help=True, help="Digitised vinyl: sync, verify, archive.")
app.add_typer(vinyl, name="vinyl")

vinyl.command()(sync.sync)
vinyl.command()(done.done)
vinyl.command()(gc.gc)
vinyl.command()(reconcile.reconcile)


def main() -> None:
    app()
