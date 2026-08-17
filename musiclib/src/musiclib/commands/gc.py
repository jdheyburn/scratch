"""`musiclib vinyl gc` — the only command that deletes."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

import typer
from rich.prompt import Confirm

from musiclib.console import console
from musiclib.state import (
    DONE_DIRNAME,
    RETENTION_DAYS,
    VINYL_ROOT,
    expired_albums,
    timestamp,
    update_state,
)


def gc(
    root: Path = typer.Option(VINYL_ROOT),
    days: int = typer.Option(RETENTION_DAYS, help="Retention window."),
    dry_run: bool = typer.Option(False),
) -> None:
    """Delete archived albums past the retention window."""
    expired = expired_albums(root, now=datetime.now().astimezone(), days=days)
    if not expired:
        console.print(f"Nothing older than {days} days.")
        raise typer.Exit()

    total = 0
    for slug, age in expired:
        d = root / DONE_DIRNAME / slug
        size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) if d.is_dir() else 0
        total += size
        console.print(f"  {slug:24} archived {age.days}d ago   {size / 1e9:.1f} GB")

    console.print(f"\n{len(expired)} album(s), {total / 1e9:.1f} GB")
    if dry_run or not Confirm.ask("Delete these permanently?", default=False):
        raise typer.Exit()

    for slug, _ in expired:
        shutil.rmtree(root / DONE_DIRNAME / slug, ignore_errors=True)
        update_state(root, slug, deleted_at=timestamp())
    console.print(f"[green]Reclaimed {total / 1e9:.1f} GB[/]")
