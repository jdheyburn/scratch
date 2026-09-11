"""The tables `dedupe` shows before it asks for anything."""

from rich.console import Console

from musictrack.commands.dedupe_views import fuzzy_preview, group_panel, summary
from musictrack.plan import MUSIC_COLLECTION, UNSORTED, build_plan

ALBUM = "https://homenormal.bandcamp.com/album/pola"
OTHER = "https://stroomtv.bandcamp.com/album/other"


def _rendered(table):
    console = Console(width=200, record=True)
    console.print(table)
    return console.export_text()


def test_the_summary_reports_every_kind_of_change(make_raindrop):
    """The table is the thing the user approves, so it has to state each
    number the run will act on."""
    old = make_raindrop(
        link=ALBUM, collection_id=UNSORTED, tags=(), created="2025-01-01T00:00:00.000Z"
    )
    new = make_raindrop(
        link=ALBUM,
        collection_id=MUSIC_COLLECTION,
        tags=("music",),
        created="2025-06-01T00:00:00.000Z",
    )
    stray = make_raindrop(link=OTHER, collection_id=UNSORTED)

    rendered = _rendered(summary(build_plan([old, new, stray])))

    for label in (
        "duplicate groups",
        "raindrops to delete",
        "survivors gaining tags",
        "survivors to file",
        "stray links to file",
    ):
        assert label in rendered


def test_the_summary_of_an_empty_plan_is_all_zeroes(make_raindrop):
    rendered = _rendered(summary(build_plan([make_raindrop(collection_id=MUSIC_COLLECTION)])))
    assert "1" not in rendered


def test_fuzzy_preview_is_none_without_a_fuzzy_group(make_raindrop):
    old = make_raindrop(link=ALBUM, created="2025-01-01T00:00:00.000Z")
    new = make_raindrop(link=ALBUM, created="2025-02-01T00:00:00.000Z")
    assert fuzzy_preview(build_plan([old, new])) is None


def test_a_group_panel_has_a_raindrop_column_for_keep_and_remove(make_raindrop):
    """Each shop link gets its own hyperlinked column pointing at the
    raindrop entry, kept apart from the shop link itself."""
    old = make_raindrop(link=ALBUM, created="2025-01-01T00:00:00.000Z")
    new = make_raindrop(link=ALBUM, created="2025-02-01T00:00:00.000Z")
    [group] = build_plan([old, new]).groups

    rendered = _rendered(group_panel(group))

    assert rendered.count("raindrop") == 2
    assert rendered.count("open") == 2
