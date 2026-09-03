"""The one console every command prints through.

Kept apart from the command modules so they can share it without importing
each other.
"""

from __future__ import annotations

from rich.console import Console

console = Console()
