"""Turning verdicts into a report."""

import pytest
from typer.testing import CliRunner

import musictrack.commands.reconcile as reconcile_module
import musictrack.commands.reconcile_walk as reconcile_walk_module
import musictrack.gather as gather_module
from musictrack.cache import SourceCache
from musictrack.cli import app
from musictrack.commands.reconcile import classify
from musictrack.commands.reconcile_views import row_table
from musictrack.console import console
from musictrack.errors import PlexError
from musictrack.match import LibraryIndex
from musictrack.models import AlbumRef


@pytest.fixture(autouse=True)
def no_plex(monkeypatch):
    """Every test here runs `reconcile`, which reads Plex over SSH unless the
    readers are patched. Tests that care patch them again on top of this."""
    monkeypatch.setattr(gather_module.plex, "album_refs", lambda: [])
    monkeypatch.setattr(gather_module.plex, "track_refs", lambda: [])


def album(artist, title):
    return AlbumRef(source="beets", artist=artist, album=title, ref="")


def want(artist, title, ref="1", source="bandcamp-wishlist", url=""):
    return AlbumRef(source=source, artist=artist, album=title, ref=ref, url=url)


def library():
    return LibraryIndex(albums=[album("Theo Parrish", "Parallel Dimensions")], tracks=[])


def test_each_candidate_lands_in_exactly_one_bucket():
    report = classify(
        [want("Theo Parrish", "Parallel Dimensions"), want("Lucy Gooch", "Rushing", ref="2")],
        library(),
        {},
    )
    assert len(report.owned) == 1
    assert len(report.absent) == 1
    assert len(report.possible) == 0


def test_a_dismissed_row_is_left_out():
    hidden = {("bandcamp-wishlist", "1"): "own the digital, want the vinyl"}
    report = classify([want("Theo Parrish", "Parallel Dimensions")], library(), hidden)
    assert report.owned == []


def test_a_dismissal_only_hides_its_own_source():
    hidden = {("spotify", "1"): "no"}
    report = classify([want("Theo Parrish", "Parallel Dimensions")], library(), hidden)
    assert len(report.owned) == 1


def test_the_report_keeps_the_library_album_that_matched():
    report = classify([want("Theo Parrish", "Parallel Dimensions")], library(), {})
    _, match = report.owned[0]
    assert match.library is not None
    assert match.library.album == "Parallel Dimensions"


# --- the command: each report reads only what it needs, and honours dismissals


class FakeDismissals:
    """Stands in for `Dismissals`: canned answers, no sqlite file touched.
    Records every `add`, so a walk's dismissals can be asserted on."""

    def __init__(self, hidden=None):
        self._hidden = hidden or {}
        self.added: list[tuple[str, str, str]] = []

    def hidden(self):
        return self._hidden

    def add(self, source, ref, reason):
        self.added.append((source, ref, reason))


def _static_walk(dismissals, deleters, title, rows, show_library, show_tier=False, plex=None):
    """A `walk` stand-in for tests that aren't about walking: prints the same
    rows as a plain table instead of prompting, so the CLI stays runnable
    without feeding stdin input."""
    console.print(row_table(title, rows, show_library, show_tier))


class RecordingBandcamp:
    """Stands in for `BandcampClient`: records which reads happened, answers
    canned lists, touches no network."""

    def __init__(self, url=""):
        self.calls: list[str] = []
        self._url = url

    def wishlist(self):
        self.calls.append("wishlist")
        return [want("Theo Parrish", "Parallel Dimensions", ref="1", url=self._url)]

    def collection(self):
        self.calls.append("collection")
        return [want("Lucy Gooch", "Rushing", ref="2", source="bandcamp-collection")]


def run(monkeypatch, tmp_path, *args, dismissed=None, raindrop_wants=None):
    """Invoke the real `reconcile` command through the CLI, with every source,
    the cache, and the dismissals store swapped for a fake or a temporary file,
    so nothing touches the network, SSH, or either real database."""
    client = RecordingBandcamp()
    monkeypatch.setattr(gather_module, "load_bandcamp_cookie", lambda: "cookie")
    monkeypatch.setattr(gather_module, "BandcampClient", lambda cookie: client)
    monkeypatch.setattr(
        gather_module.beets,
        "album_refs",
        lambda: [album("Theo Parrish", "Parallel Dimensions")],
    )
    monkeypatch.setattr(gather_module.beets, "track_refs", lambda: [])
    monkeypatch.setattr(gather_module, "spotify_client", lambda: object())
    monkeypatch.setattr(gather_module, "to_listen", lambda *a, **k: [])
    monkeypatch.setattr(gather_module, "load_token", lambda: "token")
    monkeypatch.setattr(
        gather_module, "raindrop_to_listen", lambda client: list(raindrop_wants or [])
    )
    monkeypatch.setattr(reconcile_module, "Dismissals", lambda: FakeDismissals(dismissed))
    monkeypatch.setattr(
        reconcile_module, "SourceCache", lambda: SourceCache(tmp_path / "db.sqlite")
    )
    monkeypatch.setattr(reconcile_module, "walk", _static_walk)
    result = CliRunner().invoke(app, ["reconcile", *args], env={"COLUMNS": "200"})
    return result, client


def test_backlog_only_run_does_not_read_the_wishlist(monkeypatch, tmp_path):
    _, client = run(monkeypatch, tmp_path, "--backlog")
    assert client.calls == ["collection"]


def test_wants_only_run_does_not_read_the_collection(monkeypatch, tmp_path):
    _, client = run(monkeypatch, tmp_path, "--wants")
    assert client.calls == ["wishlist"]


def test_a_default_run_reads_both(monkeypatch, tmp_path):
    _, client = run(monkeypatch, tmp_path)
    assert set(client.calls) == {"wishlist", "collection"}


def test_a_raindrop_bookmark_is_included_in_the_wants_report(monkeypatch, tmp_path):
    raindrop_want = want("Theo Parrish", "Parallel Dimensions", ref="9", source="raindrop")
    result, _ = run(monkeypatch, tmp_path, "--wants", raindrop_wants=[raindrop_want])
    assert result.exit_code == 0
    assert "raindrop:9" in result.stdout
    assert "Parallel Dimensions" in result.stdout


def test_a_dismissed_row_is_hidden_by_default_in_the_cli(monkeypatch, tmp_path):
    dismissed = {("bandcamp-wishlist", "1"): "own the digital, want the vinyl"}
    result, _ = run(monkeypatch, tmp_path, "--wants", dismissed=dismissed)
    assert result.exit_code == 0
    assert "Parallel Dimensions" not in result.stdout


def test_include_dismissed_shows_the_row_marked_with_its_reason(monkeypatch, tmp_path):
    dismissed = {("bandcamp-wishlist", "1"): "own the digital, want the vinyl"}
    result, _ = run(monkeypatch, tmp_path, "--wants", "--include-dismissed", dismissed=dismissed)
    assert result.exit_code == 0
    assert "Parallel Dimensions" in result.stdout
    assert "own the digital, want the vinyl" in result.stdout


def test_include_dismissed_marks_a_reasonless_dismissal_too(monkeypatch, tmp_path):
    dismissed = {("bandcamp-wishlist", "1"): ""}
    result, _ = run(monkeypatch, tmp_path, "--wants", "--include-dismissed", dismissed=dismissed)
    assert result.exit_code == 0
    assert "Parallel Dimensions" in result.stdout
    assert "dismissed" in result.stdout


def test_an_unwritable_dismissals_store_is_a_message_not_a_traceback(monkeypatch, tmp_path):
    """`Dismissals()` creates `~/.local/share/musictrack` on construction. An
    unwritable directory must read as a clean failure, not an escaped
    exception."""

    def boom():
        raise OSError("Permission denied")

    monkeypatch.setattr(gather_module, "load_bandcamp_cookie", lambda: "cookie")
    monkeypatch.setattr(
        reconcile_module, "SourceCache", lambda: SourceCache(tmp_path / "db.sqlite")
    )
    monkeypatch.setattr(reconcile_module, "Dismissals", boom)
    result = CliRunner().invoke(app, ["reconcile"], env={"COLUMNS": "200"})
    assert result.exit_code == 1
    assert not isinstance(result.exception, OSError)
    assert "Permission denied" in result.stdout


def test_a_locked_database_on_the_header_read_is_a_message_not_a_traceback(monkeypatch, tmp_path):
    """`gather` can succeed and still leave the header's own reads to fail:
    `source_ages` issues its own `SELECT`s against the same database, after
    the point where a plain `gather` failure would already have been caught."""
    import sqlite3

    class LockedOnFetchedAt:
        """Delegates to a real `SourceCache` for everything but `fetched_at`,
        which is where `source_ages` reads land, after `gather` has already
        succeeded and written its rows through the same delegate."""

        def __init__(self, path):
            self._real = SourceCache(path)

        def has(self, source):
            return self._real.has(source)

        def read(self, source):
            return self._real.read(source)

        def write(self, source, refs):
            return self._real.write(source, refs)

        def fetched_at(self, source):
            raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(gather_module, "load_bandcamp_cookie", lambda: "cookie")
    monkeypatch.setattr(gather_module, "BandcampClient", lambda cookie: RecordingBandcamp())
    monkeypatch.setattr(
        gather_module.beets,
        "album_refs",
        lambda: [album("Theo Parrish", "Parallel Dimensions")],
    )
    monkeypatch.setattr(gather_module.beets, "track_refs", lambda: [])
    monkeypatch.setattr(gather_module, "spotify_client", lambda: object())
    monkeypatch.setattr(gather_module, "to_listen", lambda *a, **k: [])
    monkeypatch.setattr(gather_module, "load_token", lambda: "token")
    monkeypatch.setattr(gather_module, "raindrop_to_listen", lambda client: [])
    monkeypatch.setattr(reconcile_module, "Dismissals", lambda: FakeDismissals(None))
    monkeypatch.setattr(
        reconcile_module, "SourceCache", lambda: LockedOnFetchedAt(tmp_path / "db.sqlite")
    )
    result = CliRunner().invoke(app, ["reconcile", "--wants"], env={"COLUMNS": "200"})
    assert result.exit_code == 1
    assert not isinstance(result.exception, sqlite3.OperationalError)
    assert "database is locked" in result.stdout


def test_the_backlog_table_carries_a_summary_line_of_the_other_two_buckets(monkeypatch, tmp_path):
    """The backlog table alone doesn't say where the rest of what was read
    ended up; a line under it does, without adding a fourth table."""
    result, _ = run(monkeypatch, tmp_path, "--backlog")
    assert result.exit_code == 0
    assert "0 owned, 0 worth a look" in result.stdout


# --- the cache: what a second run costs ------------------------------------


def test_a_second_run_reads_no_source(monkeypatch, tmp_path):
    """The whole point. The first run fills the cache, the second answers from
    it, and Bandcamp is not asked twice."""
    run(monkeypatch, tmp_path)
    _, client = run(monkeypatch, tmp_path)
    assert client.calls == []


def test_a_second_run_reports_the_same_rows(monkeypatch, tmp_path):
    first, _ = run(monkeypatch, tmp_path, "--wants")
    second, _ = run(monkeypatch, tmp_path, "--wants")
    assert first.exit_code == 0
    assert second.exit_code == 0
    assert "Parallel Dimensions" in first.stdout
    assert "Parallel Dimensions" in second.stdout


def test_refresh_beets_refetches_the_library_and_no_web_source(monkeypatch, tmp_path):
    run(monkeypatch, tmp_path)
    _, client = run(monkeypatch, tmp_path, "--refresh", "beets")
    assert client.calls == []


def test_refresh_bandcamp_refetches_both_lists(monkeypatch, tmp_path):
    run(monkeypatch, tmp_path)
    _, client = run(monkeypatch, tmp_path, "--refresh", "bandcamp")
    assert set(client.calls) == {"wishlist", "collection"}


def test_refresh_all_on_a_backlog_run_does_not_reach_the_wishlist(monkeypatch, tmp_path):
    run(monkeypatch, tmp_path)
    _, client = run(monkeypatch, tmp_path, "--backlog", "--refresh", "all")
    assert client.calls == ["collection"]


def test_an_unknown_refresh_name_is_a_message_not_a_traceback(monkeypatch, tmp_path):
    result, client = run(monkeypatch, tmp_path, "--refresh", "bandacmp")
    assert result.exit_code == 1
    assert "bandacmp" in result.stdout
    assert "beets" in result.stdout
    assert client.calls == []


def test_a_source_failure_is_a_message_not_a_traceback(monkeypatch, tmp_path):
    """A cold cache plus a source that refuses must still exit cleanly."""
    from musictrack.errors import BandcampError

    def boom():
        raise BandcampError("Bandcamp returned 503")

    monkeypatch.setattr(gather_module, "load_bandcamp_cookie", lambda: "cookie")
    monkeypatch.setattr(gather_module.beets, "album_refs", lambda: [])
    monkeypatch.setattr(gather_module.beets, "track_refs", lambda: [])
    monkeypatch.setattr(
        reconcile_module, "SourceCache", lambda: SourceCache(tmp_path / "db.sqlite")
    )
    monkeypatch.setattr(reconcile_module, "Dismissals", lambda: FakeDismissals(None))

    class Refusing:
        def wishlist(self):
            boom()

        def collection(self):
            boom()

    monkeypatch.setattr(gather_module, "BandcampClient", lambda cookie: Refusing())
    result = CliRunner().invoke(app, ["reconcile", "--backlog"], env={"COLUMNS": "200"})
    assert result.exit_code == 1
    assert "503" in result.stdout


def test_a_raindrop_failure_is_a_message_not_a_traceback(monkeypatch, tmp_path):
    from musictrack.errors import RaindropError

    def boom(client):
        raise RaindropError("Raindrop returned 503")

    monkeypatch.setattr(gather_module, "load_bandcamp_cookie", lambda: "cookie")
    monkeypatch.setattr(gather_module, "BandcampClient", lambda cookie: RecordingBandcamp())
    monkeypatch.setattr(gather_module.beets, "album_refs", lambda: [])
    monkeypatch.setattr(gather_module.beets, "track_refs", lambda: [])
    monkeypatch.setattr(gather_module, "spotify_client", lambda: object())
    monkeypatch.setattr(gather_module, "to_listen", lambda *a, **k: [])
    monkeypatch.setattr(gather_module, "load_token", lambda: "token")
    monkeypatch.setattr(gather_module, "raindrop_to_listen", boom)
    monkeypatch.setattr(
        reconcile_module, "SourceCache", lambda: SourceCache(tmp_path / "db.sqlite")
    )
    monkeypatch.setattr(reconcile_module, "Dismissals", lambda: FakeDismissals(None))
    result = CliRunner().invoke(app, ["reconcile", "--wants"], env={"COLUMNS": "200"})
    assert result.exit_code == 1
    assert "503" in result.stdout


# --- the age header, through the command -----------------------------------


def test_the_command_prints_the_header_before_the_tables(monkeypatch, tmp_path):
    result, _ = run(monkeypatch, tmp_path, "--wants")
    assert result.exit_code == 0
    assert "beets just now" in result.stdout
    assert result.stdout.index("beets just now") < result.stdout.index("Parallel Dimensions")


def test_a_backlog_run_does_not_claim_a_spotify_age(monkeypatch, tmp_path):
    result, _ = run(monkeypatch, tmp_path, "--backlog")
    assert result.exit_code == 0
    assert "spotify" not in result.stdout


def test_the_second_run_reports_the_cached_age_not_just_now(monkeypatch, tmp_path):
    """Proves the header reads the stored time rather than the wall clock."""
    import sqlite3
    from datetime import UTC, datetime, timedelta

    run(monkeypatch, tmp_path, "--wants")
    old = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    with sqlite3.connect(tmp_path / "db.sqlite") as db:
        db.execute("UPDATE cache_run SET fetched = ?", (old,))
    result, _ = run(monkeypatch, tmp_path, "--wants")
    assert "30 days ago" in result.stdout
    assert "--refresh" in result.stdout


# --- the walk: every row is a decision, not just a line in a table ----------


class FakeRaindropClient:
    """Stands in for `RaindropClient` inside the walk: records deletes,
    answers canned failures, touches no network."""

    def __init__(self, fail=None):
        self.deleted: list[int] = []
        self._fail = fail

    def delete(self, ids):
        if self._fail is not None:
            raise self._fail
        self.deleted.extend(ids)


class RecordingSpotifyRemove:
    """Stands in for `remove_from_playlist`: records calls, answers canned
    failures, touches no network."""

    def __init__(self, fail=None):
        self.removed: list[str] = []
        self._fail = fail

    def __call__(self, client, album_id):
        if self._fail is not None:
            raise self._fail
        self.removed.append(album_id)
        return 1


def _run_walking(
    monkeypatch,
    tmp_path,
    *args,
    dismissed=None,
    raindrop_wants=None,
    raindrop_client=None,
    spotify_wants=None,
    spotify_remove=None,
    bandcamp_url="",
    input=None,
):
    """Like `run`, but leaves the real `walk` in place so a test can drive
    its prompts with `input`."""
    client = RecordingBandcamp(url=bandcamp_url)
    monkeypatch.setattr(gather_module, "load_bandcamp_cookie", lambda: "cookie")
    monkeypatch.setattr(gather_module, "BandcampClient", lambda cookie: client)
    monkeypatch.setattr(
        gather_module.beets, "album_refs", lambda: [album("Theo Parrish", "Parallel Dimensions")]
    )
    monkeypatch.setattr(gather_module.beets, "track_refs", lambda: [])
    monkeypatch.setattr(gather_module, "spotify_client", lambda: object())
    monkeypatch.setattr(gather_module, "to_listen", lambda *a, **k: list(spotify_wants or []))
    monkeypatch.setattr(gather_module, "load_token", lambda: "token")
    monkeypatch.setattr(
        gather_module, "raindrop_to_listen", lambda client: list(raindrop_wants or [])
    )
    dismissals = FakeDismissals(dismissed)
    monkeypatch.setattr(reconcile_module, "Dismissals", lambda: dismissals)
    monkeypatch.setattr(
        reconcile_module, "SourceCache", lambda: SourceCache(tmp_path / "db.sqlite")
    )
    monkeypatch.setattr(reconcile_walk_module, "load_token", lambda: "raindrop-token")
    monkeypatch.setattr(
        reconcile_walk_module,
        "RaindropClient",
        lambda token: raindrop_client or FakeRaindropClient(),
    )
    monkeypatch.setattr(reconcile_walk_module, "_spotify_client", lambda: object())
    monkeypatch.setattr(
        reconcile_walk_module,
        "remove_from_playlist",
        spotify_remove or RecordingSpotifyRemove(),
    )
    result = CliRunner().invoke(app, ["reconcile", *args], input=input, env={"COLUMNS": "200"})
    return result, dismissals


def test_confirming_a_row_dismisses_it_with_the_given_reason(monkeypatch, tmp_path):
    result, dismissals = _run_walking(monkeypatch, tmp_path, "--wants", input="d\nduplicate\n")
    assert result.exit_code == 0
    assert dismissals.added == [("bandcamp-wishlist", "1", "duplicate")]
    assert "dismissed" in result.stdout


def test_skipping_a_row_leaves_it_alone(monkeypatch, tmp_path):
    result, dismissals = _run_walking(monkeypatch, tmp_path, "--wants", input="s\n")
    assert result.exit_code == 0
    assert dismissals.added == []
    assert "left alone" in result.stdout


def test_the_default_choice_is_skip(monkeypatch, tmp_path):
    """Pressing enter with no letter must not silently dismiss or delete."""
    result, dismissals = _run_walking(monkeypatch, tmp_path, "--wants", input="\n")
    assert result.exit_code == 0
    assert dismissals.added == []
    assert "left alone" in result.stdout


def test_an_unrecognised_letter_is_reprompted(monkeypatch, tmp_path):
    result, dismissals = _run_walking(monkeypatch, tmp_path, "--wants", input="q\ns\n")
    assert result.exit_code == 0
    assert dismissals.added == []


def test_a_reasonless_dismissal_still_dismisses(monkeypatch, tmp_path):
    result, dismissals = _run_walking(monkeypatch, tmp_path, "--wants", input="d\n\n")
    assert result.exit_code == 0
    assert dismissals.added == [("bandcamp-wishlist", "1", "")]


def test_the_backlog_row_is_walked_too(monkeypatch, tmp_path):
    result, dismissals = _run_walking(monkeypatch, tmp_path, "--backlog", input="d\ngot it\n")
    assert result.exit_code == 0
    assert dismissals.added == [("bandcamp-collection", "2", "got it")]


def test_include_dismissed_never_prompts(monkeypatch, tmp_path):
    """The audit view marks what's already decided; it must not ask for a new
    decision, so it needs no stdin input at all to complete."""
    dismissed = {("bandcamp-wishlist", "1"): "own the digital, want the vinyl"}
    result, dismissals = _run_walking(
        monkeypatch, tmp_path, "--wants", "--include-dismissed", dismissed=dismissed, input=""
    )
    assert result.exit_code == 0
    assert dismissals.added == []
    assert "own the digital, want the vinyl" in result.stdout


# --- the walk's delete option: real for Raindrop/Spotify, manual for Bandcamp


def test_deleting_a_raindrop_bookmark_also_dismisses_it(monkeypatch, tmp_path):
    raindrop_want = want("Theo Parrish", "Parallel Dimensions", ref="9", source="raindrop")
    client = FakeRaindropClient()
    result, dismissals = _run_walking(
        monkeypatch,
        tmp_path,
        "--wants",
        raindrop_wants=[raindrop_want],
        raindrop_client=client,
        input="s\nx\n",
    )
    assert result.exit_code == 0
    assert client.deleted == [9]
    assert dismissals.added == [("raindrop", "9", "deleted")]
    assert "deleted" in result.stdout


def test_a_failed_raindrop_delete_leaves_the_row_alone(monkeypatch, tmp_path):
    from musictrack.errors import RaindropError

    raindrop_want = want("Theo Parrish", "Parallel Dimensions", ref="9", source="raindrop")
    client = FakeRaindropClient(fail=RaindropError("Raindrop returned 503"))
    result, dismissals = _run_walking(
        monkeypatch,
        tmp_path,
        "--wants",
        raindrop_wants=[raindrop_want],
        raindrop_client=client,
        input="s\nx\n",
    )
    assert result.exit_code == 0
    assert dismissals.added == []
    assert "503" in result.stdout
    assert "left alone" in result.stdout


def test_deleting_a_spotify_want_also_dismisses_it(monkeypatch, tmp_path):
    spotify_want = want("Theo Parrish", "Parallel Dimensions", ref="album123", source="spotify")
    remover = RecordingSpotifyRemove()
    result, dismissals = _run_walking(
        monkeypatch,
        tmp_path,
        "--wants",
        spotify_wants=[spotify_want],
        spotify_remove=remover,
        input="s\nx\n",
    )
    assert result.exit_code == 0
    assert remover.removed == ["album123"]
    assert dismissals.added == [("spotify", "album123", "deleted")]
    assert "removed from the Spotify playlist" in result.stdout


def test_a_failed_spotify_removal_leaves_the_row_alone(monkeypatch, tmp_path):
    from musictrack.errors import SpotifyError

    spotify_want = want("Theo Parrish", "Parallel Dimensions", ref="album123", source="spotify")
    remover = RecordingSpotifyRemove(fail=SpotifyError("Spotify refused to remove tracks"))
    result, dismissals = _run_walking(
        monkeypatch,
        tmp_path,
        "--wants",
        spotify_wants=[spotify_want],
        spotify_remove=remover,
        input="s\nx\n",
    )
    assert result.exit_code == 0
    assert dismissals.added == []
    assert "refused to remove tracks" in result.stdout
    assert "left alone" in result.stdout


def test_confirming_bandcamp_removal_dismisses_it_with_a_manual_reason(monkeypatch, tmp_path):
    result, dismissals = _run_walking(
        monkeypatch,
        tmp_path,
        "--wants",
        bandcamp_url="https://artist.bandcamp.com/album/deep-rays",
        input="x\ny\n",
    )
    assert result.exit_code == 0
    assert dismissals.added == [("bandcamp-wishlist", "1", "removed manually on Bandcamp")]
    assert "https://artist.bandcamp.com/album/deep-rays" in result.stdout
    assert "removed from the Bandcamp wishlist" in result.stdout


def test_declining_bandcamp_removal_leaves_it_alone(monkeypatch, tmp_path):
    """Also covers a row with no link at all: the flow must say so rather
    than silently offering nothing to click."""
    result, dismissals = _run_walking(monkeypatch, tmp_path, "--wants", input="x\nn\n")
    assert result.exit_code == 0
    assert dismissals.added == []
    assert "no Bandcamp link on this row" in result.stdout
    assert "left alone" in result.stdout


def test_the_bandcamp_link_is_shown_up_front_not_only_after_choosing_delete(monkeypatch, tmp_path):
    """A link a human has to press (X) to reveal is a link they might never
    see if they meant to skip. The row's own listing carries it instead."""
    result, _ = _run_walking(
        monkeypatch,
        tmp_path,
        "--wants",
        bandcamp_url="https://artist.bandcamp.com/album/deep-rays",
        input="s\n",
    )
    assert result.exit_code == 0
    assert "https://artist.bandcamp.com/album/deep-rays" in result.stdout


# --- Plex: a soft-failing extra source, linked onto library matches ---------


PLEX_LINK = (
    "https://plex.example/web/index.html#!/server/0000feed/details?key=%2Flibrary%2Fmetadata%2F42"
)


def _plex_album(artist, title, ref="42", url=PLEX_LINK):
    return AlbumRef(source="plex-album", artist=artist, album=title, ref=ref, url=url)


def test_include_dismissed_passes_the_plex_link_into_the_wants_table(monkeypatch, tmp_path):
    """`--include-dismissed` prints the wants table straight from
    `wants_table(...)`, with no walk in between. This proves `plex` is really
    on that call by having a recording `wants_table` ask the real `PlexIndex`
    it was handed for the link, rather than scraping styled output the
    CliRunner would flatten to plain text anyway."""
    from musictrack.commands.reconcile_views import wants_table as real_wants_table

    monkeypatch.setattr(
        gather_module.plex,
        "album_refs",
        lambda: [_plex_album("Theo Parrish", "Parallel Dimensions")],
    )
    seen_links = []

    def recording_wants_table(rows, dismissed=None, plex=None):
        found = rows[0][1].library
        seen_links.append(plex.links(found) if plex is not None else [])
        return real_wants_table(rows, dismissed, plex)

    monkeypatch.setattr(reconcile_module, "wants_table", recording_wants_table)
    result, _ = run(monkeypatch, tmp_path, "--wants", "--include-dismissed")
    assert result.exit_code == 0
    assert seen_links == [[PLEX_LINK]]


def test_the_walk_shows_the_plex_link_of_a_match(monkeypatch, tmp_path):
    monkeypatch.setattr(
        gather_module.plex,
        "album_refs",
        lambda: [
            AlbumRef(
                source="plex-album",
                artist="Theo Parrish",
                album="Parallel Dimensions",
                ref="42",
                url=PLEX_LINK,
            )
        ],
    )
    result, _ = _run_walking(monkeypatch, tmp_path, "--wants", input="s\n")
    assert result.exit_code == 0
    assert f"plex: {PLEX_LINK}" in result.stdout


def test_a_plex_failure_warns_and_the_walk_still_runs(monkeypatch, tmp_path):
    def boom():
        raise PlexError("could not read Plex: ssh: connect: host is down")

    monkeypatch.setattr(gather_module.plex, "album_refs", boom)
    result, dismissals = _run_walking(monkeypatch, tmp_path, "--wants", input="d\nseen\n")
    assert result.exit_code == 0
    assert "no Plex links this run" in result.stdout
    assert dismissals.added == [("bandcamp-wishlist", "1", "seen")]


def test_the_age_header_names_plex_on_a_wants_run(monkeypatch, tmp_path):
    result, _ = run(monkeypatch, tmp_path, "--wants")
    assert "plex just now" in result.stdout


def test_a_backlog_run_never_reads_plex(monkeypatch, tmp_path):
    def boom():
        raise AssertionError("a backlog run read Plex")

    monkeypatch.setattr(gather_module.plex, "album_refs", boom)
    monkeypatch.setattr(gather_module.plex, "track_refs", boom)
    result, _ = run(monkeypatch, tmp_path, "--backlog")
    assert result.exit_code == 0
