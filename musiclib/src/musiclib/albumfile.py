"""`album.yaml` — the file that is yours, not the tool's.

Written at capture, hand-editable afterwards, and transferred to the server as
permanent provenance. Every write here goes through round-trip YAML so the
comments you add survive.
"""

from __future__ import annotations

from pathlib import Path

from ruamel.yaml.comments import CommentedMap

from musiclib import yamlio
from musiclib.discogs import Release


def load_album(path: Path) -> CommentedMap:
    """Read an album.yaml, keeping comments and key order intact."""
    return yamlio.load(path)


def save_album(path: Path, doc: CommentedMap) -> None:
    yamlio.dump(path, doc)


def release_snapshot(release: Release) -> CommentedMap:
    snapshot = CommentedMap()
    snapshot["artist"] = release.artist
    snapshot["album"] = release.album
    snapshot["year"] = release.year
    snapshot["label"] = release.label
    snapshot["catalogue"] = release.catalogue
    snapshot["format"] = release.format
    snapshot["tracks"] = release.tracks
    snapshot["sides"] = release.sides
    if release.side_tracks is not None:
        side_tracks = CommentedMap(release.side_tracks)
        side_tracks.fa.set_flow_style()
        snapshot["side_tracks"] = side_tracks
    return snapshot


def new_album_doc(
    discogs_id: int | None,
    discogs_url: str | None,
    cover_url: str | None,
    release: Release | None,
) -> CommentedMap:
    """Build the document written after a successful capture."""
    doc = CommentedMap()
    if release is not None:
        bits = ", ".join(b for b in [str(release.year or ""), release.label] if b)
        doc.yaml_set_start_comment(
            f"{release.artist} - {release.album}"
            + (f" ({bits}{' · ' + release.catalogue if release.catalogue else ''})" if bits else "")
        )

    doc["discogs_id"] = discogs_id
    doc["discogs_url"] = discogs_url
    doc["cover_url"] = cover_url

    if release is not None:
        doc["release"] = release_snapshot(release)
        doc.yaml_set_comment_before_after_key(
            "release",
            before="\ncached snapshot — drives the pre-flight checks and the "
            "destination name.\nedit discogs_id or cover_url above, then run:\n"
            "  musiclib vinyl sync --refresh",
        )

    return doc


def release_from_doc(doc: CommentedMap | None) -> Release | None:
    """Rebuild the cached release snapshot without re-hitting Discogs."""
    if not doc or not doc.get("release"):
        return None
    snap = doc["release"]
    side_tracks = snap.get("side_tracks")
    return Release(
        artist=snap.get("artist", ""),
        album=snap.get("album", ""),
        year=snap.get("year"),
        label=snap.get("label"),
        catalogue=snap.get("catalogue"),
        format=snap.get("format"),
        tracks=snap.get("tracks", 0),
        sides=snap.get("sides"),
        side_tracks=dict(side_tracks) if side_tracks else None,
    )
