"""Which sources a run needs, and where their rows come from."""

from datetime import UTC, datetime, timedelta

import pytest

from musictrack.cache import SourceCache
from musictrack.gather import (
    ALL,
    UnknownSource,
    keys_for,
    keys_to_refresh,
    source_ages,
)
from musictrack.models import AlbumRef

EVERY_KEY = {
    "beets",
    "beets-track",
    "bandcamp-wishlist",
    "bandcamp-collection",
    "spotify",
    "raindrop",
}


# --- which keys a run needs ------------------------------------------------


def test_a_default_run_needs_every_source():
    assert set(keys_for(True, True)) == EVERY_KEY


def test_a_wants_run_does_not_need_the_collection():
    keys = keys_for(True, False)
    assert "bandcamp-collection" not in keys
    assert {"beets", "beets-track", "bandcamp-wishlist", "spotify", "raindrop"} == set(keys)


def test_a_backlog_run_does_not_need_spotify_or_the_wishlist():
    """The reason this matters: reading Spotify means authenticating to
    Spotify. A backlog run must not do that."""
    keys = keys_for(False, True)
    assert "spotify" not in keys
    assert "bandcamp-wishlist" not in keys
    assert "raindrop" not in keys
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


def test_refreshing_raindrop_covers_only_raindrop():
    assert keys_to_refresh("raindrop") == {"raindrop"}


def test_an_unknown_name_is_an_error_that_names_the_valid_ones():
    """It must not fall back to refreshing everything. A full refetch is what
    someone who typed `--refresh bandacmp` would least expect to wait for."""
    with pytest.raises(UnknownSource) as problem:
        keys_to_refresh("bandacmp")
    message = str(problem.value)
    assert "bandacmp" in message
    for name in ("all", "beets", "bandcamp", "spotify", "raindrop"):
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
    assert names == ["beets", "bandcamp", "spotify", "raindrop"]


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


# --- read the cache, or the source -----------------------------------------


class Recorder:
    """A stand-in for a source read. Records that it was called, answers a
    canned list, touches nothing."""

    def __init__(self, refs=None, boom=None):
        self.calls = 0
        self._refs = refs if refs is not None else []
        self._boom = boom

    def __call__(self):
        self.calls += 1
        if self._boom is not None:
            raise self._boom
        return list(self._refs)


def fetchers(**overrides):
    """A fetcher for every storage key, each recording its own calls."""
    built = {key: Recorder() for key in EVERY_KEY}
    built.update(overrides)
    return built


def a_ref(source, album):
    return AlbumRef(source=source, artist="Theo Parrish", album=album, ref="1")


def test_a_source_never_read_is_fetched_and_stored(tmp_path):
    from musictrack.gather import gather

    cache = SourceCache(tmp_path / "db.sqlite")
    reads = fetchers(spotify=Recorder([a_ref("spotify", "Ugly Edits")]))
    result = gather(cache, reads, ("spotify",))
    assert reads["spotify"].calls == 1
    assert [r.album for r in result.rows["spotify"]] == ["Ugly Edits"]
    assert cache.read("spotify")[0].album == "Ugly Edits"
    assert result.fetched == {"spotify"}


def test_a_cached_source_is_not_fetched_again(tmp_path):
    from musictrack.gather import gather

    cache = SourceCache(tmp_path / "db.sqlite")
    cache.write("spotify", [a_ref("spotify", "Ugly Edits")])
    reads = fetchers()
    result = gather(cache, reads, ("spotify",))
    assert reads["spotify"].calls == 0
    assert [r.album for r in result.rows["spotify"]] == ["Ugly Edits"]
    assert result.fetched == set()


def test_a_cached_but_empty_source_is_not_fetched_again(tmp_path):
    """The bug this design exists to avoid. A wishlist that legitimately came
    back empty must read as cached, not as never read."""
    from musictrack.gather import gather

    cache = SourceCache(tmp_path / "db.sqlite")
    cache.write("bandcamp-wishlist", [])
    reads = fetchers()
    result = gather(cache, reads, ("bandcamp-wishlist",))
    assert reads["bandcamp-wishlist"].calls == 0
    assert result.rows["bandcamp-wishlist"] == []


def test_refreshing_a_name_refetches_only_its_keys(tmp_path):
    from musictrack.gather import gather

    cache = SourceCache(tmp_path / "db.sqlite")
    for key in EVERY_KEY:
        cache.write(key, [])
    reads = fetchers()
    gather(cache, reads, keys_for(True, True), refresh="beets")
    assert reads["beets"].calls == 1
    assert reads["beets-track"].calls == 1
    assert reads["bandcamp-wishlist"].calls == 0
    assert reads["bandcamp-collection"].calls == 0
    assert reads["spotify"].calls == 0


def test_refreshing_all_refetches_every_key_the_run_uses(tmp_path):
    from musictrack.gather import gather

    cache = SourceCache(tmp_path / "db.sqlite")
    for key in EVERY_KEY:
        cache.write(key, [])
    reads = fetchers()
    gather(cache, reads, keys_for(True, True), refresh=ALL)
    assert all(reads[key].calls == 1 for key in EVERY_KEY)


def test_refreshing_all_does_not_reach_a_source_the_run_does_not_need(tmp_path):
    """`--backlog --refresh all` must still not authenticate to Spotify."""
    from musictrack.gather import gather

    cache = SourceCache(tmp_path / "db.sqlite")
    for key in EVERY_KEY:
        cache.write(key, [])
    reads = fetchers()
    gather(cache, reads, keys_for(False, True), refresh=ALL)
    assert reads["spotify"].calls == 0
    assert reads["bandcamp-wishlist"].calls == 0
    assert reads["bandcamp-collection"].calls == 1


def test_a_refresh_replaces_the_stored_copy(tmp_path):
    from musictrack.gather import gather

    cache = SourceCache(tmp_path / "db.sqlite")
    cache.write("spotify", [a_ref("spotify", "Old")])
    reads = fetchers(spotify=Recorder([a_ref("spotify", "New")]))
    gather(cache, reads, ("spotify",), refresh="spotify")
    assert [r.album for r in cache.read("spotify")] == ["New"]


def test_a_failed_fetch_leaves_the_previous_copy_untouched(tmp_path):
    """A Bandcamp read that dies on page four must not replace a good copy
    with a partial one. Nothing is written until the fetch returns."""
    from musictrack.errors import BandcampError
    from musictrack.gather import gather

    cache = SourceCache(tmp_path / "db.sqlite")
    cache.write("bandcamp-wishlist", [a_ref("bandcamp-wishlist", "Kept")])
    before = cache.fetched_at("bandcamp-wishlist")
    reads = fetchers(**{"bandcamp-wishlist": Recorder(boom=BandcampError("page four"))})
    with pytest.raises(BandcampError):
        gather(cache, reads, ("bandcamp-wishlist",), refresh="bandcamp")
    assert [r.album for r in cache.read("bandcamp-wishlist")] == ["Kept"]
    assert cache.fetched_at("bandcamp-wishlist") == before


def test_an_unknown_refresh_name_fetches_nothing(tmp_path):
    """The name is validated before any source is touched, so a typo costs
    nothing but the message."""
    from musictrack.gather import gather

    cache = SourceCache(tmp_path / "db.sqlite")
    reads = fetchers()
    with pytest.raises(UnknownSource):
        gather(cache, reads, keys_for(True, True), refresh="bandacmp")
    assert all(reader.calls == 0 for reader in reads.values())


def test_the_fetchers_map_covers_every_storage_key():
    """A key with no fetcher would raise KeyError the first time a cold cache
    met it, which is the one moment the tool has to work."""
    from musictrack.gather import Fetchers

    assert set(Fetchers().as_map()) == EVERY_KEY


def test_building_the_fetchers_reads_no_credentials(monkeypatch):
    """Construction must be inert. A fully cached run never calls a fetcher,
    and so must never need the Bandcamp cookie, a Spotify token, or the
    Raindrop token."""
    import musictrack.gather as gather_module
    from musictrack.gather import Fetchers

    def boom():
        raise AssertionError("credentials read while only building the fetchers")

    monkeypatch.setattr(gather_module, "load_bandcamp_cookie", boom)
    monkeypatch.setattr(gather_module, "spotify_client", boom)
    monkeypatch.setattr(gather_module, "load_token", boom)
    Fetchers().as_map()


def test_both_bandcamp_reads_share_one_client(monkeypatch):
    """Two lists, one authenticated session. Building a second client would
    mean a second cookie read and a second summary call."""
    import musictrack.gather as gather_module
    from musictrack.gather import Fetchers

    built = []

    class FakeClient:
        def __init__(self, cookie):
            built.append(cookie)

        def wishlist(self):
            return []

        def collection(self):
            return []

    monkeypatch.setattr(gather_module, "load_bandcamp_cookie", lambda: "cookie")
    monkeypatch.setattr(gather_module, "BandcampClient", FakeClient)
    reads = Fetchers().as_map()
    reads["bandcamp-wishlist"]()
    reads["bandcamp-collection"]()
    assert built == ["cookie"]


def test_the_raindrop_fetcher_is_wired_to_the_lazy_client(monkeypatch):
    """A wiring regression here would silently drop every Raindrop want."""
    import musictrack.gather as gather_module
    from musictrack.gather import Fetchers

    built = []

    class FakeClient:
        def __init__(self, token):
            built.append(token)

    monkeypatch.setattr(gather_module, "load_token", lambda: "a-token")
    monkeypatch.setattr(gather_module, "RaindropClient", FakeClient)
    monkeypatch.setattr(gather_module, "raindrop_to_listen", lambda client: ["sentinel"])
    reads = Fetchers().as_map()
    assert reads["raindrop"]() == ["sentinel"]
    assert built == ["a-token"]


# --- the age header --------------------------------------------------------


HEADER_NOW = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)


def spans(line):
    """(text, style) for each styled span of a rich Text."""
    return [(line.plain[span.start : span.end], span.style) for span in line.spans]


def header(ages, now=HEADER_NOW):
    from rich.console import Console

    from musictrack.gather import age_line

    console = Console(width=200, record=True)
    console.print(age_line(ages, now))
    return console.export_text()


def test_the_header_names_every_source_the_run_used():
    ages = [
        ("beets", HEADER_NOW - timedelta(minutes=20)),
        ("bandcamp", HEADER_NOW - timedelta(days=4)),
        ("spotify", HEADER_NOW - timedelta(days=4)),
    ]
    rendered = header(ages)
    assert "beets 20 minutes ago" in rendered
    assert "bandcamp 4 days ago" in rendered
    assert "spotify 4 days ago" in rendered


def test_a_source_read_this_run_reads_as_just_now():
    assert "beets just now" in header([("beets", HEADER_NOW)])


def test_a_fresh_header_does_not_mention_refresh():
    ages = [("beets", HEADER_NOW), ("bandcamp", HEADER_NOW - timedelta(days=2))]
    assert "--refresh" not in header(ages)


def test_a_stale_source_puts_refresh_in_the_header():
    ages = [("beets", HEADER_NOW), ("bandcamp", HEADER_NOW - timedelta(days=30))]
    rendered = header(ages)
    assert "bandcamp 30 days ago" in rendered
    assert "--refresh" in rendered


def test_only_the_stale_entry_is_marked():
    """The warning style belongs to the old source, not to the whole line."""
    from musictrack.gather import age_line

    ages = [("beets", HEADER_NOW), ("bandcamp", HEADER_NOW - timedelta(days=30))]
    styled = {text: str(style) for text, style in spans(age_line(ages, HEADER_NOW))}
    assert "yellow" in styled["bandcamp 30 days ago"]
    assert "yellow" not in styled["beets just now"]
