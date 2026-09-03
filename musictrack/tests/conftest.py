"""Shared fixtures. Raindrops are built by hand here so each test states only
the fields it actually cares about."""

from __future__ import annotations

import itertools

import pytest

from musictrack.models import Raindrop
from musictrack.plan import MUSIC_COLLECTION

_ids = itertools.count(1)


@pytest.fixture
def make_raindrop():
    def build(
        link: str = "https://example.com/album",
        *,
        tags: tuple[str, ...] = ("music",),
        collection_id: int = MUSIC_COLLECTION,
        created: str = "2026-01-01T00:00:00.000Z",
        title: str = "An Album",
        id: int | None = None,
    ) -> Raindrop:
        return Raindrop(
            id=next(_ids) if id is None else id,
            link=link,
            title=title,
            tags=tags,
            collection_id=collection_id,
            created=created,
        )

    return build
