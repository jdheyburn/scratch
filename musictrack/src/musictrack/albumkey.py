"""What makes two releases the same release.

Two tiers. The exact tier removes only noise: case, accents, punctuation. The
loose tier also strips the things a shop and a tagger disagree about, which is
useful and destructive at once. Measured on the 2020-album library, loose
matching changes 222 keys but merges 39 albums that are different records:
Sault's three `Untitled`s become one, Biosphere's `Substrata` meets its
reissue. So a loose hit is never good enough to call something owned.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# 'ITLP09 - Pool' and 'AI-16: Bioluminescence'. Labels number their releases
# and Bandcamp keeps the number in the title where beets does not. Two patterns
# rather than one alternation, applied in this order, because that is what the
# measured counts in the spec were produced with.
CATALOGUE_COLON = re.compile(r"^[a-z]{2,4}-\d{1,3}:\s*")
CATALOGUE = re.compile(r"^[a-z]{2,6}\s?\d{1,4}\s*[-:]\s*")
BRACKETED = re.compile(r"\s*[(\[][^)\]]*[)\]]\s*$")
EDITION_TAIL = re.compile(
    r"\s+-\s+(remaster(ed)?|deluxe|expanded|reissue|mono|stereo|edition)\b.*$"
)
# Bandcamp sells 'Pitstop Box'; beets holds 'Pitstop Box LP'.
FORMAT_TAIL = re.compile(r"\s+(lp|ep)$")

# Every one of these was seen joining two artists in the real data. `•` is
# Bandcamp's, `|` is too, and beets prefers `,` and `&`.
SEPARATOR = re.compile(
    r"\s*(?:\||&|,|/|\+|•|\bfeat\.?\b|\bft\.?\b|\bwith\b|\bvs\.?\b|\band\b)\s*",
    re.IGNORECASE,
)

VARIOUS_NAMES = {"various", "various artists", "va"}


def _fold(text: str) -> str:
    """Accents off, so `zakè` and `zake` are the same artist."""
    return unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()


def key(text: str) -> str:
    """The exact tier. Removes nothing a person would call part of the title."""
    return re.sub(r"[^a-z0-9]+", " ", _fold(text).lower()).strip()


def loose(text: str) -> str:
    """The exact tier, plus the decorations shops and taggers disagree about."""
    working = _fold(text).lower()
    working = EDITION_TAIL.sub("", CATALOGUE.sub("", CATALOGUE_COLON.sub("", working)))
    previous = None
    while previous != working:
        previous = working
        working = BRACKETED.sub("", working)
    plain = re.sub(r"[^a-z0-9]+", " ", working).strip().removeprefix("the ")
    return FORMAT_TAIL.sub("", plain).strip()


@dataclass(frozen=True)
class ArtistSet:
    """The artists on a release, as names that can be compared.

    `various` is a value of its own rather than a name in the set. 76 library
    albums are compilations, and treating `Various Artists` as an ordinary
    artist would match every one of them against every other.
    """

    names: frozenset[str]
    various: bool = False


def artists(name: str) -> ArtistSet:
    """Split a credit into comparable names."""
    if key(name) in VARIOUS_NAMES:
        return ArtistSet(frozenset(), various=True)
    parts = (key(part) for part in SEPARATOR.split(name or ""))
    return ArtistSet(frozenset(part for part in parts if part))


def agree(left: ArtistSet, right: ArtistSet) -> bool:
    """One shared name is enough.

    Bandcamp credits `36` where beets credits `36 & zakè`. Requiring the whole
    credit to match would lose every collaboration.
    """
    if left.various or right.various:
        return left.various and right.various
    return bool(left.names & right.names)
