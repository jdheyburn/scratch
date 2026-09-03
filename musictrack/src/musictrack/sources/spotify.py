"""The only module that talks to Spotify.

The album, not the track, is the unit. Albums are added to the playlist whole:
6359 entries are 675 albums, and 670 of those are the complete album by track
count. So entries are grouped by album id and a repeated album is expected.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from musictrack.config import SPOTIFY_DIR, load_spotify_credentials
from musictrack.errors import SpotifyError
from musictrack.models import AlbumRef

PLAYLIST_NAME = "To Listen"
REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPE = "playlist-read-private playlist-read-collaborative"
PAGE_SIZE = 100


def spotify_client(cache_path: Path | None = None):
    """An authenticated client, using the token cached by the first login."""
    import spotipy

    client_id, client_secret = load_spotify_credentials()
    return spotipy.Spotify(
        auth_manager=spotipy.SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            # Spotify rejects `localhost`; the loopback address is required.
            redirect_uri=REDIRECT_URI,
            scope=SCOPE,
            cache_path=str(cache_path or SPOTIFY_DIR / "token.json"),
            open_browser=False,
        )
    )


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
    result = client.current_user_playlists(limit=50)
    while result:
        for playlist in result.get("items") or []:
            if playlist and (playlist.get("name") or "").strip().lower() == wanted:
                return playlist["id"]
        result = client.next(result) if result.get("next") else None
    raise SpotifyError(f"no playlist named {name!r} in this account")


def to_listen(client, name: str = PLAYLIST_NAME) -> list[AlbumRef]:
    """Every album in the playlist, once each."""
    playlist_id = find_playlist(client, name)
    entries: list[dict] = []
    offset = 0
    while True:
        page = client.playlist_items(playlist_id, limit=PAGE_SIZE, offset=offset)
        items = page.get("items") or []
        if not items:
            break
        entries.extend(items)
        offset += len(items)
        if offset >= page.get("total", 0):
            break
    return album_blocks(entries)
