"""Which tags mean something, and what a survivor inherits.

Roughly half the tags on the account are batch-save stamps in one of two
formats. Copying a later stamp onto an earlier bookmark would record something
false, so they are dropped on the way in. The survivor keeps its own.

The two formats are disjoint eras, not variants: `June 25 2024` ran to
2025-03, `12/07/2026` from 2025-04 onward. A format that changed once can
change again, and the failure would be silent — an unrecognised stamp stops
looking like a date and gets merged. `looks_like_an_unknown_date` makes that
case loud instead.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

# `12/07/2026` and `June 25 2024`, the two formats found on the account. The
# comma is optional because `December 3, 2023` appears both ways. Only full
# month names are recognised; abbreviated names like `Aug` are unknown dates.
DATE_TAG = re.compile(
    r"^(\d{1,2}/\d{1,2}/\d{4}|(?:January|February|March|April|May|June|July|August"
    r"|September|October|November|December) \d{1,2},? \d{4})$"
)

# A four-digit year anywhere in the tag, or a slash-separated pattern with
# 2-digit years. Used only to notice a date shape we don't recognise; no real
# tag on the account contains a year.
YEARISH = re.compile(r"(?:^|\D)(?:19|20)\d{2}(?:\D|$)|\d+/\d+/\d+")


def is_date_tag(tag: str) -> bool:
    """True for a batch-save stamp, false for a tag that means something."""
    return DATE_TAG.match(tag) is not None


def looks_like_an_unknown_date(tag: str) -> bool:
    """A tag carrying a year that neither known format explains.

    Held back from merges and reported. It may be a third date format, in
    which case merging it would stamp a bookmark with a date it was never
    saved on; or it may be a real tag like `best-of-2026`, in which case
    holding it back loses something. Both are recoverable once seen, and
    neither is if it happens quietly.
    """
    return not is_date_tag(tag) and YEARISH.search(tag) is not None


def mergeable(tag: str) -> bool:
    """Whether a tag may travel from a duplicate onto the survivor."""
    return not is_date_tag(tag) and not looks_like_an_unknown_date(tag)


def merge_tags(survivor: Sequence[str], extras: Iterable[Sequence[str]]) -> tuple[str, ...]:
    """The survivor's tags, plus every real tag its duplicates carried.

    Sorted so the result is the same however the extras were ordered — which
    is what lets a caller compare it against the survivor's current tags to
    decide whether a write is needed at all.
    """
    inherited = {tag for extra in extras for tag in extra if mergeable(tag)}
    return tuple(sorted(set(survivor) | inherited))


def held_back(extras: Iterable[Sequence[str]]) -> tuple[str, ...]:
    """Unknown-date-shaped tags the merge refused, for the command to report."""
    return tuple(sorted({t for extra in extras for t in extra if looks_like_an_unknown_date(t)}))
