"""Which sources a run needs, and where their rows come from."""

from datetime import UTC, datetime

import pytest

from musictrack.cache import SourceCache
from musictrack.gather import (
    ALL,
    UnknownSource,
    keys_for,
    keys_to_refresh,
    source_ages,
)

EVERY_KEY = {"beets", "beets-track", "bandcamp-wishlist", "bandcamp-collection", "spotify"}


# --- which keys a run needs ------------------------------------------------


def test_a_default_run_needs_every_source():
    assert set(keys_for(True, True)) == EVERY_KEY


def test_a_wants_run_does_not_need_the_collection():
    keys = keys_for(True, False)
    assert "bandcamp-collection" not in keys
    assert {"beets", "beets-track", "bandcamp-wishlist", "spotify"} == set(keys)


def test_a_backlog_run_does_not_need_spotify_or_the_wishlist():
    """The reason this matters: reading Spotify means authenticating to
    Spotify. A backlog run must not do that."""
    keys = keys_for(False, True)
    assert "spotify" not in keys
    assert "bandcamp-wishlist" not in keys
    assert {"beets", "beets-track", "bandcamp-collection"} == set(keys)


def test_the_library_is_needed_by_both_and_listed_once():
    keys = keys_for(True, True)
    assert keys.count("beets") == 1
    assert keys.count("beets-track") == 1


# --- which keys a refresh name covers --------------------------------------


def test_no_refresh_refreshes_nothing():
    assert keys_to_refresh(None) == frozenset()


def test_refreshing_all_covers_every_key():
    assert keys_to_refresh(ALL) == EVERY_KEY


def test_refreshing_beets_covers_both_dumps():
    assert keys_to_refresh("beets") == {"beets", "beets-track"}


def test_refreshing_bandcamp_covers_both_lists():
    assert keys_to_refresh("bandcamp") == {"bandcamp-wishlist", "bandcamp-collection"}


def test_refreshing_spotify_covers_only_spotify():
    assert keys_to_refresh("spotify") == {"spotify"}


def test_an_unknown_name_is_an_error_that_names_the_valid_ones():
    """It must not fall back to refreshing everything. A full refetch is what
    someone who typed `--refresh bandacmp` would least expect to wait for."""
    with pytest.raises(UnknownSource) as problem:
        keys_to_refresh("bandacmp")
    message = str(problem.value)
    assert "bandacmp" in message
    for name in ("all", "beets", "bandcamp", "spotify"):
        assert name in message


def test_a_storage_key_is_not_a_refresh_name():
    """`beets-track` is how a row is stored, not something the user names."""
    with pytest.raises(UnknownSource):
        keys_to_refresh("beets-track")


# --- ages, grouped the way the user names sources --------------------------


def test_ages_are_reported_per_refresh_name_not_per_storage_key(tmp_path):
    cache = SourceCache(tmp_path / "db.sqlite")
    for key in EVERY_KEY:
        cache.write(key, [])
    names = [name for name, _ in source_ages(cache, keys_for(True, True))]
    assert names == ["beets", "bandcamp", "spotify"]


def test_a_name_whose_keys_the_run_did_not_use_is_left_out(tmp_path):
    cache = SourceCache(tmp_path / "db.sqlite")
    for key in EVERY_KEY:
        cache.write(key, [])
    names = [name for name, _ in source_ages(cache, keys_for(False, True))]
    assert names == ["beets", "bandcamp"]


def test_a_name_covering_two_keys_reports_the_older_of_them(tmp_path):
    """Both beets dumps come from one SSH session and normally share a
    timestamp. If they ever disagree, the header must not flatter the pair."""
    cache = SourceCache(tmp_path / "db.sqlite")
    cache.write("beets", [])
    cache.write("beets-track", [])
    older = datetime(2026, 1, 1, tzinfo=UTC)
    import sqlite3

    with sqlite3.connect(tmp_path / "db.sqlite") as db:
        db.execute(
            "UPDATE cache_run SET fetched = ? WHERE source = ?", (older.isoformat(), "beets")
        )
    [(name, when)] = [
        pair for pair in source_ages(cache, ("beets", "beets-track")) if pair[0] == "beets"
    ]
    assert name == "beets"
    assert when == older


def test_a_never_read_source_reports_no_age(tmp_path):
    cache = SourceCache(tmp_path / "db.sqlite")
    assert source_ages(cache, ("spotify",)) == [("spotify", None)]


def test_the_row_a_source_age_describes_is_an_album_ref_source(tmp_path):
    """Guards the mapping: every storage key in REFRESH_NAMES must be a value
    some source adapter actually stamps onto an AlbumRef."""
    from musictrack.gather import REFRESH_NAMES

    covered = {key for keys in REFRESH_NAMES.values() for key in keys}
    assert covered == EVERY_KEY
