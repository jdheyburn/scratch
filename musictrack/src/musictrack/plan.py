"""What the tool intends to do, worked out in full before anything is written.

Nothing here performs I/O. The command reads once, builds a Plan, shows it, and
only then writes — so the table you approve is exactly what runs.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from musictrack.identity import normalise
from musictrack.models import Raindrop
from musictrack.tags import held_back, merge_tags

MUSIC_COLLECTION = 29207263
UNSORTED = -1


def is_music(raindrop: Raindrop) -> bool:
    """Half the music links are tagged but stranded in Unsorted, so the tag
    and the collection each have to count on their own."""
    return "music" in raindrop.tags or raindrop.collection_id == MUSIC_COLLECTION


@dataclass(frozen=True)
class Group:
    """One bookmark saved more than once, and what becomes of each copy."""

    survivor: Raindrop
    extras: tuple[Raindrop, ...]
    merged_tags: tuple[str, ...]
    held_back_tags: tuple[str, ...]

    @property
    def needs_retag(self) -> bool:
        """False when the extras carried nothing the survivor lacks, which is
        the usual case — writing then would be a wasted request."""
        return self.merged_tags != tuple(sorted(set(self.survivor.tags)))

    @property
    def needs_move(self) -> bool:
        """Only Unsorted survivors move. A survivor already filed somewhere
        real is left alone, which is what keeps two real collections from
        needing a winner."""
        return self.survivor.collection_id == UNSORTED


@dataclass(frozen=True)
class Plan:
    """Every write the run will make, in the order it will make them."""

    groups: tuple[Group, ...]
    strays: tuple[Raindrop, ...]

    @property
    def retags(self) -> tuple[tuple[int, tuple[str, ...]], ...]:
        return tuple((g.survivor.id, g.merged_tags) for g in self.groups if g.needs_retag)

    @property
    def survivor_moves(self) -> tuple[int, ...]:
        return tuple(g.survivor.id for g in self.groups if g.needs_move)

    @property
    def deletions(self) -> tuple[int, ...]:
        return tuple(extra.id for g in self.groups for extra in g.extras)

    @property
    def stray_moves(self) -> tuple[int, ...]:
        return tuple(s.id for s in self.strays)

    @property
    def held_back_tags(self) -> tuple[str, ...]:
        """Unknown-date-shaped tags no survivor inherited. Empty on the
        account as it stands; non-empty means the tag format has drifted and
        wants a look before the run is trusted."""
        return tuple(sorted({t for g in self.groups for t in g.held_back_tags}))


def build_plan(raindrops: Sequence[Raindrop]) -> Plan:
    """Music links in, every intended write out.

    Sorting by id before grouping makes the result independent of the order
    the API happened to return pages in.

    The same id twice in the input would group a raindrop with itself: one copy
    deleted, the other kept and moved. The client dedupes as it pages, so this
    should never arrive, but keying by id here makes that state unrepresentable
    whoever does the reading. The first copy wins, matching the client, so the
    two dedupes cannot disagree about which one they kept.
    """
    by_id: dict[int, Raindrop] = {}
    for raindrop in raindrops:
        if is_music(raindrop):
            by_id.setdefault(raindrop.id, raindrop)
    music = sorted(by_id.values(), key=lambda r: r.id)

    by_url: dict[str, list[Raindrop]] = defaultdict(list)
    for raindrop in music:
        by_url[normalise(raindrop.link)].append(raindrop)

    groups = []
    spoken_for = set()
    for url in sorted(by_url):
        copies = by_url[url]
        if len(copies) < 2:
            continue
        # `created` is ISO 8601, so text order is chronological order. The id
        # breaks ties between two saves in the same millisecond.
        survivor, *extras = sorted(copies, key=lambda r: (r.created, r.id))
        groups.append(
            Group(
                survivor=survivor,
                extras=tuple(extras),
                merged_tags=merge_tags(survivor.tags, [e.tags for e in extras]),
                held_back_tags=held_back([e.tags for e in extras]),
            )
        )
        spoken_for.update(r.id for r in copies)

    strays = tuple(r for r in music if r.collection_id == UNSORTED and r.id not in spoken_for)
    return Plan(groups=tuple(groups), strays=strays)
