"""Deciding what a record actually is — the only part that needs you."""

from __future__ import annotations

from pathlib import Path

from musiclib.albumfile import load_album, new_album_doc, release_snapshot, save_album
from musiclib.cover import fetch_cover, upgrade_image_url
from musiclib.discogs import Release, extract_release_id, fetch_release
from musiclib.errors import DiscogsError
from musiclib.net import http_get

SKIP_WORDS = {"skip", "none", "n/a"}


def capture(
    directory: Path,
    token: str,
    get=http_get,
    ask=None,
    confirm=None,
    echo=print,
) -> bool:
    """Prompt for the release and the cover, then write album.yaml and cover.jpg.

    Nothing is written until both are settled, so abandoning leaves no trace.
    Returns False if you gave up on this album.
    """
    release: Release | None = None
    discogs_id: int | None = None
    discogs_url: str | None = None

    while True:
        typed = ask(f"  Discogs release for {directory.name} (id, url, or 'skip')").strip()
        if not typed:
            return False
        if typed.lower() in SKIP_WORDS:
            break

        release_id = extract_release_id(typed)
        if release_id is None:
            echo(f"  ! {typed!r} is not a release id or url")
            continue
        try:
            found = fetch_release(release_id, token=token, get=get)
        except DiscogsError as e:
            echo(f"  ! {e}")
            continue

        bits = " / ".join(str(b) for b in [found.year, found.label, found.catalogue] if b)
        echo(f"  -> {found.artist} - {found.album}  [discogs {release_id}]")
        echo(f"    {bits}")
        echo(f"    {found.tracks} tracks, sides={found.sides or '?'}")
        if confirm("    Correct release?"):
            release, discogs_id = found, release_id
            discogs_url = f"https://www.discogs.com/release/{release_id}"
            break

    cover_url: str | None = None
    cover_bytes: bytes | None = None
    while cover_bytes is None:
        answer = ask("  Cover image url (or 'skip')").strip()
        # Never discard a confirmed release just because the artwork failed:
        # finding the right release is the part that took effort. Without a
        # cover the album is stopped at pre-flight, which is the point.
        if not answer or answer.lower() in SKIP_WORDS:
            cover_url = None
            break
        cover_url = upgrade_image_url(answer)
        try:
            cover, cover_bytes = fetch_cover(cover_url, get=get)
        except DiscogsError as e:
            echo(f"  ! {e}")
            continue
        echo(f"    cover {cover.width}x{cover.height}")

    if cover_bytes is not None:
        (directory / "cover.jpg").write_bytes(cover_bytes)
    save_album(
        directory / "album.yaml",
        new_album_doc(discogs_id, discogs_url, cover_url, release),
    )
    return True


def refresh_album(directory: Path, token: str, get=http_get) -> bool:
    """Re-fetch the release snapshot and the artwork from album.yaml as edited.

    This is what makes hand-editing the file meaningful: correct the id or
    point cover_url somewhere better, then refresh.
    """
    doc_path = directory / "album.yaml"
    if not doc_path.is_file():
        return False

    doc = load_album(doc_path)
    discogs_id = doc.get("discogs_id")
    release = None
    if discogs_id is not None:
        release = fetch_release(int(discogs_id), token=token, get=get)

    cover_url = upgrade_image_url(str(doc.get("cover_url") or ""))
    if cover_url:
        _, data = fetch_cover(cover_url, get=get)
        (directory / "cover.jpg").write_bytes(data)

    # Edit in place rather than rebuilding: a rebuilt document loses every
    # comment you added, which is the whole reason this file is yours to edit.
    if cover_url:
        doc["cover_url"] = cover_url
    if release is not None:
        doc["release"] = release_snapshot(release)
    save_album(doc_path, doc)
    return True
