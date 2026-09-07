"""Turning verdicts into a report."""

from rich.console import Console
from typer.testing import CliRunner

import musictrack.commands.reconcile as reconcile_module
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
    reason to an empty string, so a plain dismissal is the ordinary case,
    not an edge case. `.get()` returning "" must not read the same as
    `.get()` returning None for a row that was never dismissed."""
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


def run(monkeypatch, *args, dismissed=None):
    """Invoke the real `reconcile` command through the CLI, with every source
    and the dismissals store swapped for a fake, so nothing touches the
    network, SSH, or the real dismissals database."""
    client = RecordingBandcamp()
    monkeypatch.setattr(reconcile_module, "load_bandcamp_cookie", lambda: "cookie")
    monkeypatch.setattr(reconcile_module, "BandcampClient", lambda cookie: client)
    monkeypatch.setattr(
        reconcile_module.beets,
        "album_refs",
        lambda: [album("Theo Parrish", "Parallel Dimensions")],
    )
    monkeypatch.setattr(reconcile_module.beets, "track_refs", lambda: [])
    monkeypatch.setattr(reconcile_module, "spotify_client", lambda: object())
    monkeypatch.setattr(reconcile_module, "to_listen", lambda *a, **k: [])
    monkeypatch.setattr(reconcile_module, "Dismissals", lambda: FakeDismissals(dismissed))
    result = CliRunner().invoke(app, ["reconcile", *args], env={"COLUMNS": "200"})
    return result, client


def test_backlog_only_run_does_not_read_the_wishlist(monkeypatch):
    _, client = run(monkeypatch, "--backlog")
    assert client.calls == ["collection"]


def test_wants_only_run_does_not_read_the_collection(monkeypatch):
    _, client = run(monkeypatch, "--wants")
    assert client.calls == ["wishlist"]


def test_a_default_run_reads_both(monkeypatch):
    _, client = run(monkeypatch)
    assert set(client.calls) == {"wishlist", "collection"}


def test_a_dismissed_row_is_hidden_by_default_in_the_cli(monkeypatch):
    dismissed = {("bandcamp-wishlist", "1"): "own the digital, want the vinyl"}
    result, _ = run(monkeypatch, "--wants", dismissed=dismissed)
    assert result.exit_code == 0
    assert "Parallel Dimensions" not in result.stdout


def test_include_dismissed_shows_the_row_marked_with_its_reason(monkeypatch):
    dismissed = {("bandcamp-wishlist", "1"): "own the digital, want the vinyl"}
    result, _ = run(monkeypatch, "--wants", "--include-dismissed", dismissed=dismissed)
    assert result.exit_code == 0
    assert "Parallel Dimensions" in result.stdout
    assert "own the digital, want the vinyl" in result.stdout


def test_include_dismissed_marks_a_reasonless_dismissal_too(monkeypatch):
    dismissed = {("bandcamp-wishlist", "1"): ""}
    result, _ = run(monkeypatch, "--wants", "--include-dismissed", dismissed=dismissed)
    assert result.exit_code == 0
    assert "Parallel Dimensions" in result.stdout
    assert "dismissed" in result.stdout
