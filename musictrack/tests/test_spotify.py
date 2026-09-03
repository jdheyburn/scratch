"""Reading the To Listen playlist. The Spotify client is a fake; no test
authenticates or reaches the network."""

import pytest

from musictrack.errors import SpotifyError
from musictrack.sources.spotify import album_blocks, entry_album, find_playlist, to_listen


def entry(album_id, name="An Album", artists=("An Artist",), key="item"):
    return {
        key: {
            "name": "A Track",
            "album": {
                "id": album_id,
                "name": name,
                "album_type": "album",
                "total_tracks": 3,
                "artists": [{"name": a} for a in artists],
                "external_urls": {"spotify": f"https://open.spotify.com/album/{album_id}"},
            },
        }
    }


class FakeSpotify:
    def __init__(self, playlists, items=()):
        self._playlists = playlists
        self._items = list(items)

    def current_user_playlists(self, limit=50):
        return {"items": self._playlists, "next": None}

    def playlist_items(self, playlist_id, limit=100, offset=0):
        window = self._items[offset : offset + limit]
        return {"items": window, "total": len(self._items)}

    def next(self, result):
        return None


def test_the_entry_is_read_from_item_not_track():
    """Spotify moved playlist entries from `track` to `item`. spotipy and every
    example still say `track`, so both are read."""
    from_item = entry_album(entry("a1", key="item"))
    from_track = entry_album(entry("a1", key="track"))
    assert from_item is not None and from_item["id"] == "a1"
    assert from_track is not None and from_track["id"] == "a1"


def test_an_entry_with_no_album_is_skipped():
    assert entry_album({"item": None}) is None
    assert entry_album({"item": {"album": {}}}) is None


def test_a_run_of_tracks_collapses_to_one_album():
    """6359 playlist entries are 675 albums. A repeated album id is the normal
    case, not a duplicate."""
    blocks = album_blocks([entry("a1"), entry("a1"), entry("a1"), entry("a2")])
    assert [b.ref for b in blocks] == ["a1", "a2"]


def test_a_block_carries_the_album_artists_not_the_track_artists():
    [block] = album_blocks([entry("a1", artists=("Stevia", "Susumu Yokota"))])
    assert block.artist == "Stevia, Susumu Yokota"
    assert block.source == "spotify"


def test_the_playlist_is_matched_by_exact_name():
    """A substring test grabs 'Pitchblack Playback: Music To Listen To In The
    Dark' instead."""
    client = FakeSpotify(
        [
            {"id": "decoy", "name": "Pitchblack Playback: Music To Listen To In The Dark"},
            {"id": "real", "name": "To Listen"},
        ]
    )
    assert find_playlist(client) == "real"


def test_a_missing_playlist_is_an_error_not_an_empty_report():
    client = FakeSpotify([{"id": "x", "name": "Something Else"}])
    with pytest.raises(SpotifyError) as problem:
        find_playlist(client)
    assert "To Listen" in str(problem.value)


def test_a_null_playlist_entry_does_not_crash_the_listing():
    client = FakeSpotify([None, {"id": "real", "name": "To Listen"}])
    assert find_playlist(client) == "real"


def test_to_listen_returns_one_ref_per_album():
    client = FakeSpotify(
        [{"id": "real", "name": "To Listen"}],
        items=[entry("a1"), entry("a1"), entry("a2")],
    )
    assert [r.ref for r in to_listen(client)] == ["a1", "a2"]
