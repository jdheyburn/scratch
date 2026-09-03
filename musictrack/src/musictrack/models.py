"""One bookmark, as much of it as this tool needs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Raindrop:
    """A Raindrop.io bookmark.

    `created` stays the ISO 8601 string the API returns. It is only ever
    compared against another one, and ISO 8601 sorts correctly as text.
    """

    id: int
    link: str
    title: str
    tags: tuple[str, ...]
    collection_id: int
    created: str
