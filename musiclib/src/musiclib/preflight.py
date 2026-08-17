"""Everything checkable before a byte moves."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from musiclib.cover import COVER_MIN_WIDTH, COVER_PREFERRED_WIDTH, Cover, prepare_cover
from musiclib.discogs import Release
from musiclib.errors import BadCover
from musiclib.tags import album_flacs


@dataclass(frozen=True)
class Candidate:
    """An album directory as observed on disk, plus its resolved release."""

    slug: str
    flac_count: int
    aup3_count: int
    release: Release | None
    cover: Cover | None


@dataclass(frozen=True)
class Finding:
    severity: str  # "stop" | "warn"
    message: str


def observe(directory: Path, release: Release | None) -> Candidate:
    """What the filesystem says about an album, paired with its release."""
    cover = None
    cover_path = directory / "cover.jpg"
    if cover_path.is_file():
        try:
            cover, _ = prepare_cover(cover_path.read_bytes())
        except BadCover:
            # An unreadable cover is no cover — stop the album, don't crash.
            cover = None
    return Candidate(
        slug=directory.name,
        flac_count=len(album_flacs(directory)),
        aup3_count=len(list(directory.glob("*.aup3"))),
        release=release,
        cover=cover,
    )


def preflight(candidate: Candidate) -> list[Finding]:
    """Everything checkable before a byte moves. Stops exclude, warnings inform."""
    findings: list[Finding] = []
    release = candidate.release

    if release is not None and candidate.flac_count != release.tracks:
        findings.append(
            Finding(
                "stop",
                f"{candidate.flac_count} FLACs but the release has {release.tracks} tracks",
            )
        )

    if (
        release is not None
        and release.sides is not None
        and candidate.aup3_count
        and candidate.aup3_count != release.sides
    ):
        findings.append(
            Finding(
                "warn",
                f"{candidate.aup3_count} .aup3 projects but the release has {release.sides} sides",
            )
        )

    if candidate.cover is None:
        findings.append(Finding("stop", "no usable cover image"))
    elif candidate.cover.width < COVER_MIN_WIDTH:
        findings.append(
            Finding(
                "stop",
                f"cover is {candidate.cover.width}px wide; beets rejects "
                f"anything under {COVER_MIN_WIDTH}px",
            )
        )
    elif candidate.cover.width < COVER_PREFERRED_WIDTH:
        findings.append(
            Finding(
                "warn",
                f"cover is only {candidate.cover.width}px wide",
            )
        )

    return findings


def is_blocked(findings: list[Finding]) -> bool:
    """A stop excludes the album from the run; warnings only inform."""
    return any(f.severity == "stop" for f in findings)


def destination_name(release: Release | None, discogs_id: int | None, slug: str) -> str:
    """Directory name on dee. Derived from the release so two records can't collide."""
    if release is None or discogs_id is None:
        return f"{slug} (no-id)"

    def safe(s: str) -> str:
        # Match beets' default replacement so names agree with the library.
        return s.replace("/", "_").replace("\\", "_").strip()

    return f"{safe(release.artist)} - {safe(release.album)} ({discogs_id})"
