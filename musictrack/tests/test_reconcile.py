"""Turning verdicts into a report."""

from rich.console import Console
from typer.testing import CliRunner

import musictrack.commands.reconcile as reconcile_module
import musictrack.gather as gather_module
from musictrack.cache import SourceCache
from musictrack.cli import app
from musictrack.commands.reconcile import backlog_table, classify, possible_table, wants_table
from musictrack.match import LibraryIndex
from musictrack.models import AlbumRef


def album(artist, title):
    return AlbumRef(source="beets", artist=artist, album=title, ref="")


def want(artist, title, ref="1", source="bandcamp-wishlist"):
    return AlbumRef(source=source, artist=artist, album=title, ref=ref)


def library():
    return LibraryIndex(albums=[album("Theo Parrish", "Parallel Dimensions")], tracks=[])


def render(table):
    """A table's cell text, wide enough that nothing wraps and hides a match."""
    console = Console(width=200, record=True)
    console.print(table)
    return console.export_text()


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


# --- the tier that hit, shown only on the needs-a-look table ---------------


def test_the_possible_table_names_the_tier_that_matched():
    # "LP" survives the exact key but not the loose one, so this is an
    # album-loose hit: worth a look, not owned outright.
    report = classify([want("Theo Parrish", "Parallel Dimensions LP")], library(), {})
    assert len(report.possible) == 1
    rendered = render(possible_table(report))
    assert "album-loose" in rendered


def test_the_wants_table_has_no_tier_column():
    report = classify([want("Theo Parrish", "Parallel Dimensions")], library(), {})
    rendered = render(wants_table(report))
    assert "tier" not in rendered


def test_the_backlog_table_has_no_tier_column():
    report = classify([want("Lucy Gooch", "Rushing")], library(), {})
    rendered = render(backlog_table(report))
    assert "tier" not in rendered


# --- marking a dismissed row when it is shown anyway ------------------------


def test_a_table_without_marking_carries_no_dismissed_column():
    report = classify([want("Theo Parrish", "Parallel Dimensions")], library(), {})
    rendered = render(wants_table(report))
    assert "dismissed" not in rendered


def test_a_shown_dismissed_row_is_marked_with_its_reason():
    report = classify([want("Theo Parrish", "Parallel Dimensions")], library(), {})
    dismissed = {("bandcamp-wishlist", "1"): "own the digital, want the vinyl"}
    rendered = render(wants_table(report, dismissed))
    assert "own the digital, want the vinyl" in rendered


def test_a_row_that_was_never_dismissed_stays_unmarked():
    lib = LibraryIndex(
        albums=[album("Theo Parrish", "Parallel Dimensions"), album("Lucy Gooch", "Rushing")],
        tracks=[],
    )
    report = classify(
        [
            want("Theo Parrish", "Parallel Dimensions", ref="1"),
            want("Lucy Gooch", "Rushing", ref="2"),
        ],
        lib,
        {},
    )
    assert len(report.owned) == 2
    dismissed = {("bandcamp-wishlist", "1"): "own the digital, want the vinyl"}
    rendered = render(wants_table(report, dismissed))
    lucy_lines = [line for line in rendered.splitlines() if "Lucy Gooch" in line]
    assert lucy_lines
    assert "dismissed:" not in lucy_lines[0]


def test_a_dismissal_with_no_reason_is_still_marked():
    """`Dismissals.add` and `musictrack dismiss --reason` both default the
    reason to an empty string, so a plain dismissal is the ordinary case, not
    an edge case. The table marks a row by whether its key is present in
    `dismissed`, not by whether the reason is truthy, so an empty reason still
    reads as dismissed rather than as never dismissed."""
    report = classify([want("Theo Parrish", "Parallel Dimensions")], library(), {})
    dismissed = {("bandcamp-wishlist", "1"): ""}
    rendered = render(wants_table(report, dismissed))
    lines = [line for line in rendered.splitlines() if "Theo Parrish" in line]
    assert lines
    assert "dismissed" in lines[0]


def test_the_three_dismissal_states_are_distinguishable():
    """Never dismissed, dismissed with a reason, and dismissed with the
    empty-reason default must each render differently in the same table."""
    lib = LibraryIndex(
        albums=[
            album("Theo Parrish", "Parallel Dimensions"),
            album("Lucy Gooch", "Rushing"),
            album("Overmono", "Good Lies"),
        ],
        tracks=[],
    )
    report = classify(
        [
            want("Theo Parrish", "Parallel Dimensions", ref="1"),
            want("Lucy Gooch", "Rushing", ref="2"),
            want("Overmono", "Good Lies", ref="3"),
        ],
        lib,
        {},
    )
    assert len(report.owned) == 3
    dismissed = {
        ("bandcamp-wishlist", "1"): "duplicate",
        ("bandcamp-wishlist", "2"): "",
    }
    rendered = render(wants_table(report, dismissed))

    def line_for(artist):
        [found] = [line for line in rendered.splitlines() if artist in line]
        return found

    assert "dismissed: duplicate" in line_for("Theo Parrish")
    reasonless = line_for("Lucy Gooch")
    assert "dismissed" in reasonless
    assert "dismissed:" not in reasonless
    assert "dismissed" not in line_for("Overmono")


# --- the command: each report reads only what it needs, and honours dismissals


class FakeDismissals:
    """Stands in for `Dismissals`: canned answers, no sqlite file touched."""

    def __init__(self, hidden=None):
        self._hidden = hidden or {}

    def hidden(self):
        return self._hidden


class RecordingBandcamp:
    """Stands in for `BandcampClient`: records which reads happened, answers
    canned lists, touches no network."""

    def __init__(self):
        self.calls: list[str] = []

    def wishlist(self):
        self.calls.append("wishlist")
        return [want("Theo Parrish", "Parallel Dimensions", ref="1")]

    def collection(self):
        self.calls.append("collection")
        return [want("Lucy Gooch", "Rushing", ref="2", source="bandcamp-collection")]


def run(monkeypatch, tmp_path, *args, dismissed=None):
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
    monkeypatch.setattr(reconcile_module, "Dismissals", lambda: FakeDismissals(dismissed))
    monkeypatch.setattr(
        reconcile_module, "SourceCache", lambda: SourceCache(tmp_path / "db.sqlite")
    )
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
