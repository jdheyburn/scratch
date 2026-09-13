"""Walking `reconcile`'s rows one at a time: skip, dismiss, or (for a
Raindrop bookmark) delete it outright, folding review and cleanup into a
single pass instead of a separate `dismiss <source>:<ref>` call after the
fact — the one write `reconcile` makes, against Raindrop only."""

from __future__ import annotations

import typer

from musictrack.commands.reconcile_views import Row, row_table
from musictrack.config import load_token
from musictrack.console import console
from musictrack.errors import MissingToken, RaindropError
from musictrack.raindrop import RaindropClient
from musictrack.store import Dismissals


def _choose(prompt: str, letters: str, default: str) -> str:
    """A beets-import-style choice: type one letter (case-insensitive) or
    press enter for the default. Re-prompts on anything else."""
    while True:
        answer = typer.prompt(prompt, default=default, show_default=False).strip().lower()
        if answer in letters:
            return answer


class LazyRaindropClient:
    """Builds a `RaindropClient` on first use, not on every row: most runs
    delete nothing, so most runs never touch the token file."""

    def __init__(self) -> None:
        self._client: RaindropClient | None = None

    def get(self) -> RaindropClient:
        if self._client is None:
            self._client = RaindropClient(load_token())
        return self._client


def walk(
    dismissals: Dismissals,
    raindrop: LazyRaindropClient,
    title: str,
    rows: list[Row],
    show_library: bool,
    show_tier: bool = False,
) -> None:
    for candidate, match in rows:
        console.print(row_table(title, [(candidate, match)], show_library, show_tier))
        is_raindrop = candidate.source == "raindrop"
        prompt = (
            "(S)kip, (D)ismiss, delete the raindrop bookmar(X)"
            if is_raindrop
            else "(S)kip, (D)ismiss"
        )
        choice = _choose(prompt, "sdx" if is_raindrop else "sd", "s")
        if choice == "d":
            reason = typer.prompt("reason", default="", show_default=False)
            dismissals.add(candidate.source, candidate.ref, reason)
            console.print("[green]dismissed[/]")
        elif choice == "x":
            try:
                raindrop.get().delete([int(candidate.ref)])
            except (MissingToken, RaindropError) as problem:
                console.print(f"[red]{problem}[/]")
                console.print("[dim]left alone[/]")
                continue
            dismissals.add(candidate.source, candidate.ref, "deleted")
            console.print("[green]raindrop bookmark deleted[/]")
        else:
            console.print("[dim]left alone[/]")
