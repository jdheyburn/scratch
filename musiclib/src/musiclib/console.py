"""What we print, and what we run on your behalf.

Kept apart from the command modules so they can all share one console without
importing each other.
"""

from __future__ import annotations

import shlex
import subprocess

from rich.console import Console

console = Console()


def run(cmd: list[str], dry_run: bool = False) -> int:
    if dry_run:
        console.print(f"[dim]would run:[/] {shlex.join(cmd)}")
        return 0
    return subprocess.call(cmd)
