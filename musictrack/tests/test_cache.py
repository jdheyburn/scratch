"""A copy of what each source last said."""

from datetime import UTC, datetime

from musictrack.cache import SourceCache
from musictrack.models import AlbumRef


def ref(artist="Theo Parrish", album="Parallel Dimensions", source="bandcamp-wishlist", **kw):
    return AlbumRef(
        source=source, artist=artist, album=album, ref=kw.get("ref", "1"), url=kw.get("url", "")
    )


def test_rows_survive_a_round_trip(tmp_path):
    cache = SourceCache(tmp_path / "db.sqlite")
    cache.write("bandcamp-wishlist", [ref(url="https://example.com/a")])
    assert cache.read("bandcamp-wishlist") == [ref(url="https://example.com/a")]


def test_a_beets_row_keeps_its_empty_ref_and_url(tmp_path):
    """Beets rows carry no id and no url. Both must come back as empty strings
    rather than as None, because AlbumRef declares them as str."""
    cache = SourceCache(tmp_path / "db.sqlite")
    original = AlbumRef(source="beets", artist="Nala Sinephro", album="Endlessness", ref="")
    cache.write("beets", [original])
    [restored] = cache.read("beets")
    assert restored == original
    assert restored.ref == ""
    assert restored.url == ""


def test_rows_keep_the_order_they_were_written_in(tmp_path):
    cache = SourceCache(tmp_path / "db.sqlite")
    written = [
        ref(album="First", ref="1"),
        ref(album="Second", ref="2"),
        ref(album="Third", ref="3"),
    ]
    cache.write("bandcamp-wishlist", written)
    albums = [r.album for r in cache.read("bandcamp-wishlist")]
    assert albums == ["First", "Second", "Third"]


def test_a_source_that_returned_nothing_still_counts_as_fetched(tmp_path):
    """The distinction the whole design turns on. A source can legitimately
    return zero rows, and that is not the same as never having been read. If
    `has` were computed from the row count, an empty wishlist would be
    refetched forever."""
    cache = SourceCache(tmp_path / "db.sqlite")
    cache.write("bandcamp-wishlist", [])
    assert cache.has("bandcamp-wishlist") is True
    assert cache.read("bandcamp-wishlist") == []


def test_a_source_never_written_has_not_been_fetched(tmp_path):
    cache = SourceCache(tmp_path / "db.sqlite")
    assert cache.has("bandcamp-wishlist") is False
    assert cache.fetched_at("bandcamp-wishlist") is None
    assert cache.read("bandcamp-wishlist") == []


def test_writing_again_replaces_rather_than_appends(tmp_path):
    cache = SourceCache(tmp_path / "db.sqlite")
    cache.write("spotify", [ref(source="spotify", album="Old", ref="1")])
    cache.write("spotify", [ref(source="spotify", album="New", ref="2")])
    rows = cache.read("spotify")
    assert len(rows) == 1
    assert rows[0].album == "New"


def test_each_source_is_stored_separately(tmp_path):
    cache = SourceCache(tmp_path / "db.sqlite")
    cache.write("bandcamp-wishlist", [ref(album="Wanted")])
    cache.write("bandcamp-collection", [ref(source="bandcamp-collection", album="Bought")])
    assert [r.album for r in cache.read("bandcamp-wishlist")] == ["Wanted"]
    assert [r.album for r in cache.read("bandcamp-collection")] == ["Bought"]


def test_a_read_row_carries_the_source_it_was_stored_under(tmp_path):
    cache = SourceCache(tmp_path / "db.sqlite")
    cache.write("beets-track", [AlbumRef(source="beets-track", artist="A", album="B", ref="")])
    assert cache.read("beets-track")[0].source == "beets-track"


def test_the_fetch_time_is_recorded_and_timezone_aware(tmp_path):
    before = datetime.now(UTC)
    cache = SourceCache(tmp_path / "db.sqlite")
    cache.write("spotify", [])
    when = cache.fetched_at("spotify")
    assert when is not None
    assert when.tzinfo is not None
    assert before <= when <= datetime.now(UTC)


def test_the_cache_survives_being_reopened(tmp_path):
    path = tmp_path / "db.sqlite"
    SourceCache(path).write("beets", [AlbumRef("beets", "A", "B", "")])
    assert len(SourceCache(path).read("beets")) == 1


def test_the_parent_directory_is_created(tmp_path):
    cache = SourceCache(tmp_path / "nested" / "deeper" / "db.sqlite")
    cache.write("beets", [])
    assert cache.has("beets")


def test_the_cache_shares_a_database_with_dismissals_without_disturbing_them(tmp_path):
    """Both live in `musictrack.db`. Creating one must not drop the other's
    table, and writing to one must not touch the other's rows."""
    from musictrack.store import Dismissals

    path = tmp_path / "db.sqlite"
    dismissals = Dismissals(path)
    dismissals.add("spotify", "abc", "own the digital")
    cache = SourceCache(path)
    cache.write("spotify", [ref(source="spotify")])
    assert Dismissals(path).hidden() == {("spotify", "abc"): "own the digital"}
    assert len(cache.read("spotify")) == 1
