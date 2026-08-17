"""Round-trip YAML, shared by album.yaml and the state files.

Round-trip mode is the point: album.yaml is yours to hand-edit, and a rewrite
that dropped your comments would make editing it pointless.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML


def yaml() -> YAML:
    y = YAML()
    y.preserve_quotes = True
    y.indent(mapping=2, sequence=4, offset=2)
    return y


def load(path: Path) -> Any:
    """Read a document, keeping comments and key order intact."""
    with path.open("r", encoding="utf-8") as fh:
        return yaml().load(fh)


def dump(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as fh:
        yaml().dump(data, fh)
