"""Which Plex album a library match is."""

from musictrack.cache import SourceCache
from musictrack.errors import PlexError
from musictrack.models import AlbumRef
from musictrack.plexindex import PlexIndex, load_plex


def beets_album(artist, title):
    return AlbumRef(source="beets", artist=artist, album=title, ref="")


def beets_track(artist, title):
    return AlbumRef(source="beets-track", artist=artist, album=title, ref="")


def plex_album(artist, title, album_id):
    return AlbumRef(
        source="plex-album", artist=artist, album=title, ref=album_id, url=f"plex/{album_id}"
    )


def plex_track(artist, title, album_id):
    return AlbumRef(
        source="plex-track", artist=artist, album=title, ref=album_id, url=f"plex/{album_id}"
    )


def test_an_album_match_links_to_its_plex_album():
    index = PlexIndex([plex_album("Theo Parrish", "Parallel Dimensions", "1")], [])
    assert index.links(beets_album("Theo Parrish", "Parallel Dimensions")) == ["plex/1"]


def test_a_track_match_links_to_the_album_the_track_is_on():
    """The prompt for all this: a wishlist `Untitled` matched a track called
    `[untitled]` on another record, and nothing said which."""
    index = PlexIndex([], [plex_track("Huerco S.", "[untitled]", "9")])
    assert index.links(beets_track("Huerco S.", "[untitled]")) == ["plex/9"]


def test_a_track_on_two_albums_links_to_both():
    index = PlexIndex(
        [],
        [
            plex_track("Daphni", "Clap Your Hands", "1"),
            plex_track("Daphni", "Clap Your Hands", "2"),
        ],
    )
    assert index.links(beets_track("Daphni", "Clap Your Hands")) == ["plex/1", "plex/2"]


def test_the_same_album_is_linked_once():
    index = PlexIndex(
        [],
        [
            plex_track("Daphni", "Clap Your Hands", "1"),
            plex_track("Daphni", "Clap Your Hands", "1"),
        ],
    )
    assert index.links(beets_track("Daphni", "Clap Your Hands")) == ["plex/1"]


def test_an_album_match_never_links_to_a_track_of_the_same_title():
    index = PlexIndex([], [plex_track("Warmth", "Parallel", "1")])
    assert index.links(beets_album("Warmth", "Parallel")) == []


def test_an_artist_spelled_differently_still_links_when_the_title_is_unique():
    """92 of 2020 beets albums name their artist differently from Plex."""
    index = PlexIndex([plex_album("Jimmy Pop", "Hooray For Boobies", "1")], [])
    assert index.links(beets_album("Bloodhound Gang", "Hooray For Boobies")) == ["plex/1"]


def test_an_ambiguous_title_with_no_agreeing_artist_links_nowhere():
    index = PlexIndex(
        [plex_album("Somebody", "Untitled", "1"), plex_album("Somebody Else", "Untitled", "2")], []
    )
    assert index.links(beets_album("Huerco S.", "Untitled")) == []


def test_a_disagreeing_artist_is_ignored_when_an_agreeing_one_exists():
    index = PlexIndex(
        [plex_album("Somebody", "Untitled", "1"), plex_album("Huerco S.", "Untitled", "2")], []
    )
    assert index.links(beets_album("Huerco S.", "Untitled")) == ["plex/2"]


def test_no_match_links_nowhere():
    assert PlexIndex([], []).links(beets_album("Lucy Gooch", "Rushing")) == []


def test_no_library_record_links_nowhere():
    assert PlexIndex([plex_album("A", "B", "1")], []).links(None) == []


def test_a_title_that_folds_to_nothing_links_nowhere():
    index = PlexIndex([plex_album("A", "ー", "1")], [])
    assert index.links(beets_album("A", "ー")) == []


def test_the_empty_index_links_nowhere():
    assert PlexIndex.empty().links(beets_album("Theo Parrish", "Parallel Dimensions")) == []


def test_load_plex_builds_an_index_from_both_dumps(tmp_path):
    fetchers = {
        "plex-album": lambda: [plex_album("Theo Parrish", "Parallel Dimensions", "1")],
        "plex-track": lambda: [plex_track("Huerco S.", "[untitled]", "9")],
    }
    index = load_plex(SourceCache(tmp_path / "db.sqlite"), fetchers, None)
    assert index.links(beets_track("Huerco S.", "[untitled]")) == ["plex/9"]


def test_a_failed_plex_read_is_an_empty_index_and_a_warning(tmp_path, capsys):
    def boom():
        raise PlexError("could not read Plex: ssh: connect: host is down")

    cache = SourceCache(tmp_path / "db.sqlite")
    index = load_plex(cache, {"plex-album": boom, "plex-track": boom}, None)
    assert index.links(beets_album("Theo Parrish", "Parallel Dimensions")) == []
    assert "no Plex links" in capsys.readouterr().out
    assert not cache.has("plex-album")


def test_a_partial_plex_failure_caches_the_successful_key(tmp_path, capsys):
    """When plex-album succeeds but plex-track fails, only plex-album is cached."""

    def boom():
        raise PlexError("plex-track read failed")

    cache = SourceCache(tmp_path / "db.sqlite")
    fetchers = {
        "plex-album": lambda: [plex_album("Theo Parrish", "Parallel Dimensions", "1")],
        "plex-track": boom,
    }
    index = load_plex(cache, fetchers, None)
    assert index.links(beets_album("Theo Parrish", "Parallel Dimensions")) == []
    assert "no Plex links" in capsys.readouterr().out
    assert cache.has("plex-album")
    assert not cache.has("plex-track")
