"""Walking `reconcile`'s rows one at a time: skip, dismiss, or (for a source
that supports it) delete the underlying entry, folding review and cleanup
into a single pass instead of a separate `dismiss <source>:<ref>` call after
the fact. Raindrop and Spotify delete for real; Bandcamp has no write API,
so its delete shows a link and takes the human's word that they used it."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

import typer
from rich.prompt import Prompt

from musictrack.commands.reconcile_views import Row, row_listing
from musictrack.config import load_token
from musictrack.console import console
from musictrack.errors import MissingToken, RaindropError, SpotifyError
from musictrack.models import AlbumRef
from musictrack.raindrop import RaindropClient
from musictrack.sources.spotify import remove_from_playlist
from musictrack.sources.spotify import spotify_client as _spotify_client
from musictrack.store import Dismissals

SKIP = "[bold cyan]S[/bold cyan]kip"
DISMISS = "[bold cyan]D[/bold cyan]ismiss"
DELETE_ERRORS = (MissingToken, RaindropError, SpotifyError)


@dataclass
class Deleter:
    """One source's delete action: what to call, how to describe it before
    and after, and what reason to record locally — a source with no delete
    action is simply absent from the table `walk` is given.

    `action` returns whether the delete actually happened: always `True` for
    a source with a real write API, but Bandcamp has none, so its action
    shows a link and asks the human to confirm they did it themselves —
    `False` on a decline means the row is left alone, not dismissed."""

    prompt_label: str
    done_label: str
    dismiss_reason: str
    action: Callable[[AlbumRef], bool]


class LazyRaindropClient:
    """Builds a `RaindropClient` on first use, not on every row: most runs
    delete nothing, so most runs never touch the token file."""

    def __init__(self) -> None:
        self._client: RaindropClient | None = None

    def get(self) -> RaindropClient:
        if self._client is None:
            self._client = RaindropClient(load_token())
        return self._client


class LazySpotifyClient:
    """Builds a Spotify client on first use, not on every row: most runs
    delete nothing, so most runs never force the OAuth handshake."""

    def __init__(self) -> None:
        self._client = None

    def get(self):
        if self._client is None:
            self._client = _spotify_client()
        return self._client


def _delete_raindrop(client: LazyRaindropClient, candidate: AlbumRef) -> bool:
    client.get().delete([int(candidate.ref)])
    return True


def raindrop_deleter(client: LazyRaindropClient) -> Deleter:
    return Deleter(
        prompt_label="the Raindrop bookmark",
        done_label="raindrop bookmark deleted",
        dismiss_reason="deleted",
        action=lambda candidate: _delete_raindrop(client, candidate),
    )


def _remove_from_playlist(client: LazySpotifyClient, candidate: AlbumRef) -> bool:
    remove_from_playlist(client.get(), candidate.ref)
    return True


def spotify_deleter(client: LazySpotifyClient) -> Deleter:
    return Deleter(
        prompt_label="from the Spotify playlist",
        done_label="removed from the Spotify playlist",
        dismiss_reason="deleted",
        action=lambda candidate: _remove_from_playlist(client, candidate),
    )


def _confirm_bandcamp_removal(candidate: AlbumRef) -> bool:
    """Bandcamp has no published write API, so there is nothing to call —
    show the wishlist page and ask whether the human removed it there."""
    if candidate.url:
        console.print(f"  {candidate.url}")
    else:
        console.print("[yellow]no Bandcamp link on this row[/]")
    return typer.confirm("Removed it from the Bandcamp wishlist?", default=False)


def bandcamp_deleter() -> Deleter:
    return Deleter(
        prompt_label="from Bandcamp (manual)",
        done_label="removed from the Bandcamp wishlist",
        dismiss_reason="removed manually on Bandcamp",
        action=_confirm_bandcamp_removal,
    )


def _choose(prompt: str, letters: str, default: str) -> str:
    """A beets-import-style choice: type one letter (case-insensitive) or
    press enter for the default. Re-prompts on anything else. The prompt
    carries Rich markup, colouring each shortcut letter the way beets
    highlights its own import-time choices."""
    while True:
        answer = Prompt.ask(prompt, console=console, default=default, show_default=False)
        answer = answer.strip().lower()
        if answer in letters:
            return answer


def walk(
    dismissals: Dismissals,
    deleters: Mapping[str, Deleter],
    title: str,
    rows: list[Row],
    show_library: bool,
    show_tier: bool = False,
) -> None:
    if not rows:
        return
    console.print(f"[bold underline]{title}[/bold underline]")
    for candidate, match in rows:
        console.print(row_listing(candidate, match, show_library, show_tier))
        deleter = deleters.get(candidate.source)
        prompt = f"{SKIP}, {DISMISS}"
        if deleter is not None:
            prompt += f", [bold cyan](X)[/bold cyan] delete {deleter.prompt_label}"
        choice = _choose(prompt, "sdx" if deleter is not None else "sd", "s")
        if choice == "d":
            reason = typer.prompt("reason", default="", show_default=False)
            dismissals.add(candidate.source, candidate.ref, reason)
            console.print("[green]dismissed[/]")
        elif choice == "x":
            assert deleter is not None
            try:
                done = deleter.action(candidate)
            except DELETE_ERRORS as problem:
                console.print(f"[red]{problem}[/]")
                console.print("[dim]left alone[/]")
                console.print()
                continue
            if done:
                dismissals.add(candidate.source, candidate.ref, deleter.dismiss_reason)
                console.print(f"[green]{deleter.done_label}[/]")
            else:
                console.print("[dim]left alone[/]")
        else:
            console.print("[dim]left alone[/]")
        console.print()
