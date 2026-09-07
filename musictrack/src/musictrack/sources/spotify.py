"""The only module that talks to Spotify.

The album, not the track, is the unit. Albums are added to the playlist whole:
6359 entries are 675 albums, and 670 of those are the complete album by track
count. So entries are grouped by album id and a repeated album is expected.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import requests
import spotipy
from spotipy import SpotifyException
from spotipy.oauth2 import SpotifyOauthError

from musictrack.config import SPOTIFY_DIR, load_spotify_credentials
from musictrack.errors import SpotifyError
from musictrack.models import AlbumRef

PLAYLIST_NAME = "To Listen"
REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPE = "playlist-read-private playlist-read-collaborative"
PAGE_SIZE = 100

# 6359 playlist entries at 100 a page is 64 pages. This bounds a misbehaving
# API rather than a real playlist, the same role bandcamp.py's MAX_PAGES plays.
MAX_PAGES = 100

SPOTIFY_ERRORS = (SpotifyException, SpotifyOauthError, requests.RequestException)


def _call(operation: str, fn, *args, **kwargs):
    """Run one spotipy call, turning what it raises into `SpotifyError`.

    The wrapped message carries the operation and the status, nothing from
    the original exception. A spotipy exception can carry request context,
    and that context must never reach a printed message.
    """
    try:
        return fn(*args, **kwargs)
    except SPOTIFY_ERRORS as exc:
        status = getattr(exc, "http_status", None)
        detail = f" (status {status})" if status else ""
        raise SpotifyError(f"Spotify refused to {operation}{detail}") from exc


def spotify_client(cache_path: Path | None = None):
    """An authenticated client, using the token cached by the first login."""
    client_id, client_secret = load_spotify_credentials()
    auth_manager = _call(
        "set up Spotify authentication",
        spotipy.SpotifyOAuth,
        client_id=client_id,
        client_secret=client_secret,
        # Spotify rejects `localhost`; the loopback address is required.
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        cache_path=str(cache_path or SPOTIFY_DIR / "token.json"),
        open_browser=False,
    )
    return spotipy.Spotify(auth_manager=auth_manager)


def entry_album(entry: dict) -> dict | None:
    """The album an entry belongs to, or nothing if it has none.

    Spotify serves the entry under `item`. Its own documentation, and spotipy,
    still say `track`, so both are read and whichever exists wins.
    """
    holder = (entry or {}).get("item") or (entry or {}).get("track") or {}
    album = holder.get("album") or {}
    return album if album.get("id") else None


def album_blocks(entries: Iterable[dict]) -> list[AlbumRef]:
    """One ref per album, in the order the albums first appear."""
    blocks: dict[str, AlbumRef] = {}
    for entry in entries:
        album = entry_album(entry)
        if album is None or album["id"] in blocks:
            continue
        blocks[album["id"]] = AlbumRef(
            source="spotify",
            artist=", ".join(a.get("name", "") for a in album.get("artists") or []),
            album=album.get("name") or "",
            ref=album["id"],
            url=(album.get("external_urls") or {}).get("spotify", ""),
        )
    return list(blocks.values())


def find_playlist(client, name: str = PLAYLIST_NAME) -> str:
    """The playlist's id, matched on the whole name.

    Not a substring test: the account also holds `Pitchblack Playback: Music To
    Listen To In The Dark`, which contains this name and is not it.
    """
    wanted = name.strip().lower()
    result = _call("list the playlists", client.current_user_playlists, limit=50)
    for _ in range(MAX_PAGES):
        for playlist in (result or {}).get("items") or []:
            if playlist and (playlist.get("name") or "").strip().lower() == wanted:
                return playlist["id"]
        if not result or not result.get("next"):
            raise SpotifyError(f"no playlist named {name!r} in this account")
        result = _call("list the playlists", client.next, result)
    raise SpotifyError(f"stopped after {MAX_PAGES} pages of playlists")


def to_listen(client, name: str = PLAYLIST_NAME) -> list[AlbumRef]:
    """Every album in the playlist, once each."""
    playlist_id = find_playlist(client, name)
    entries: list[dict] = []
    offset = 0
    total: int | None = None
    for _ in range(MAX_PAGES):
        page = _call(
            "read the playlist",
            client.playlist_items,
            playlist_id,
            limit=PAGE_SIZE,
            offset=offset,
        )
        if total is None:
            total = page.get("total")
        items = page.get("items") or []
        if not items:
            break
        entries.extend(items)
        offset += len(items)
    else:
        raise SpotifyError(f"stopped after {MAX_PAGES} pages of the playlist")
    if total is not None and len(entries) < total:
        raise SpotifyError(
            f"read {len(entries)} of {total} playlist entries; the paged read lost records"
        )
    return album_blocks(entries)
