"""How `reconcile` shows a row: the bulk table and the walk's single-row
listing."""

from rich.console import Console

from musictrack.commands.reconcile import classify
from musictrack.commands.reconcile_views import (
    backlog_table,
    possible_table,
    row_listing,
    wants_table,
)
from musictrack.match import LibraryIndex
from musictrack.models import AlbumRef


def album(artist, title):
    return AlbumRef(source="beets", artist=artist, album=title, ref="")


def want(artist, title, ref="1", source="bandcamp-wishlist", url=""):
    return AlbumRef(source=source, artist=artist, album=title, ref=ref, url=url)


def library():
    return LibraryIndex(albums=[album("Theo Parrish", "Parallel Dimensions")], tracks=[])


def render(table):
    """A table's cell text, wide enough that nothing wraps and hides a match."""
    console = Console(width=200, record=True)
    console.print(table)
    return console.export_text()


# --- the tier that hit, shown only on the needs-a-look table ---------------


def test_the_possible_table_names_the_tier_that_matched():
    # "LP" survives the exact key but not the loose one, so this is an
    # album-loose hit: worth a look, not owned outright.
    report = classify([want("Theo Parrish", "Parallel Dimensions LP")], library(), {})
    assert len(report.possible) == 1
    rendered = render(possible_table(report.possible))
    assert "album-loose" in rendered


def test_the_wants_table_has_no_tier_column():
    report = classify([want("Theo Parrish", "Parallel Dimensions")], library(), {})
    rendered = render(wants_table(report.owned))
    assert "tier" not in rendered


def test_the_backlog_table_has_no_tier_column():
    report = classify([want("Lucy Gooch", "Rushing")], library(), {})
    rendered = render(backlog_table(report.absent))
    assert "tier" not in rendered


# --- marking a dismissed row when it is shown anyway ------------------------


def test_a_table_without_marking_carries_no_dismissed_column():
    report = classify([want("Theo Parrish", "Parallel Dimensions")], library(), {})
    rendered = render(wants_table(report.owned))
    assert "dismissed" not in rendered


def test_a_shown_dismissed_row_is_marked_with_its_reason():
    report = classify([want("Theo Parrish", "Parallel Dimensions")], library(), {})
    dismissed = {("bandcamp-wishlist", "1"): "own the digital, want the vinyl"}
    rendered = render(wants_table(report.owned, dismissed))
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
    rendered = render(wants_table(report.owned, dismissed))
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
    rendered = render(wants_table(report.owned, dismissed))
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
    rendered = render(wants_table(report.owned, dismissed))

    def line_for(artist):
        [found] = [line for line in rendered.splitlines() if artist in line]
        return found

    assert "dismissed: duplicate" in line_for("Theo Parrish")
    reasonless = line_for("Lucy Gooch")
    assert "dismissed" in reasonless
    assert "dismissed:" not in reasonless
    assert "dismissed" not in line_for("Overmono")


# --- the walk's single-row listing, beets-import style ----------------------


def test_the_listing_headlines_artist_and_album():
    report = classify([want("Theo Parrish", "Parallel Dimensions")], library(), {})
    [(candidate, match)] = report.owned
    rendered = render(row_listing(candidate, match, show_library=True))
    assert "Theo Parrish - Parallel Dimensions" in rendered


def test_a_library_match_is_shown_when_asked_for():
    report = classify([want("Theo Parrish", "Parallel Dimensions")], library(), {})
    [(candidate, match)] = report.owned
    rendered = render(row_listing(candidate, match, show_library=True))
    assert "in the library as: Theo Parrish / Parallel Dimensions" in rendered


def test_no_library_line_without_a_match():
    report = classify([want("Lucy Gooch", "Rushing")], library(), {})
    [(candidate, match)] = report.absent
    rendered = render(row_listing(candidate, match, show_library=False))
    assert "in the library as" not in rendered


def test_the_tier_only_appears_when_asked_for():
    report = classify([want("Theo Parrish", "Parallel Dimensions LP")], library(), {})
    [(candidate, match)] = report.possible
    with_tier = render(row_listing(candidate, match, show_library=True, show_tier=True))
    without_tier = render(row_listing(candidate, match, show_library=True, show_tier=False))
    assert "tier: album-loose" in with_tier
    assert "tier:" not in without_tier


def test_the_id_always_appears():
    report = classify([want("Theo Parrish", "Parallel Dimensions", ref="42")], library(), {})
    [(candidate, match)] = report.owned
    rendered = render(row_listing(candidate, match, show_library=True))
    assert "id: bandcamp-wishlist:42" in rendered


def test_a_link_is_shown_when_the_row_carries_one():
    report = classify(
        [want("Theo Parrish", "Parallel Dimensions", url="https://x.bandcamp.com/album/y")],
        library(),
        {},
    )
    [(candidate, match)] = report.owned
    rendered = render(row_listing(candidate, match, show_library=True))
    assert "https://x.bandcamp.com/album/y" in rendered


def test_no_link_line_without_one():
    report = classify([want("Theo Parrish", "Parallel Dimensions")], library(), {})
    [(candidate, match)] = report.owned
    rendered = render(row_listing(candidate, match, show_library=True))
    assert "link:" not in rendered
