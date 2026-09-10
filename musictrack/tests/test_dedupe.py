"""The command: what it shows, and the order in which it writes."""

import json
from pathlib import Path

from rich.console import Console
from typer.testing import CliRunner

import musictrack.commands.dedupe as dedupe_module
from musictrack.cli import app
from musictrack.commands.dedupe import apply_dedupe, apply_filing, fuzzy_preview, summary
from musictrack.errors import MissingToken, RaindropError
from musictrack.plan import MUSIC_COLLECTION, UNSORTED, build_plan
from musictrack.raindrop import to_raindrop

ALBUM = "https://homenormal.bandcamp.com/album/pola"
OTHER = "https://stroomtv.bandcamp.com/album/other"

# This repo is public, so the fixture is trimmed to music links only (plus
# titles stripped, since the tool never reads them) and does not carry the
# real account's non-music bookmarks, which are personal — finance, journal,
# notes. `test_no_non_music_link_is_touched` needs some non-music records to
# stay meaningful, so it carries ~20 fabricated ones instead (900000xxx ids,
# example.com links, no `music` tag, not in the music collection).
FIXTURE = Path(__file__).parent / "fixtures" / "raindrops.json"


class RecordingClient:
    """Remembers what it was asked to do, and in what order."""

    def __init__(self):
        self.actions = []

    def set_tags(self, raindrop_id, tags):
        self.actions.append(("retag", raindrop_id, tuple(tags)))

    def move(self, ids, collection_id):
        if not ids:
            return
        self.actions.append(("move", tuple(ids), collection_id))

    def delete(self, ids):
        if not ids:
            return
        self.actions.append(("delete", tuple(ids)))


def test_tags_are_merged_before_the_extra_is_deleted(make_raindrop):
    """The ordering that makes a half-finished run safe: if the delete never
    happens, nothing is lost; if the retag never happens, the extra is still
    there to try again."""
    old = make_raindrop(link=ALBUM, tags=(), created="2024-12-16T00:00:00.000Z")
    new = make_raindrop(
        link=ALBUM, tags=("December 16 2024", "music"), created="2024-12-16T12:00:00.000Z"
    )
    client = RecordingClient()
    apply_dedupe(client, build_plan([old, new]))
    kinds = [action[0] for action in client.actions]
    assert kinds.index("retag") < kinds.index("delete")


def test_the_survivor_is_moved_before_the_extra_is_deleted(make_raindrop):
    old = make_raindrop(link=ALBUM, collection_id=UNSORTED, created="2025-01-01T00:00:00.000Z")
    new = make_raindrop(
        link=ALBUM, collection_id=MUSIC_COLLECTION, created="2025-06-01T00:00:00.000Z"
    )
    client = RecordingClient()
    apply_dedupe(client, build_plan([old, new]))
    kinds = [action[0] for action in client.actions]
    assert kinds.index("move") < kinds.index("delete")


def test_survivors_are_moved_into_the_music_collection(make_raindrop):
    old = make_raindrop(link=ALBUM, collection_id=UNSORTED, created="2025-01-01T00:00:00.000Z")
    new = make_raindrop(link=ALBUM, collection_id=UNSORTED, created="2025-06-01T00:00:00.000Z")
    client = RecordingClient()
    apply_dedupe(client, build_plan([old, new]))
    assert ("move", (old.id,), MUSIC_COLLECTION) in client.actions


def test_dedupe_does_not_touch_the_strays(make_raindrop):
    """Filing is a separate confirmation, so declining it must leave the
    strays where they are."""
    stray = make_raindrop(link=OTHER, collection_id=UNSORTED)
    client = RecordingClient()
    apply_dedupe(client, build_plan([stray]))
    assert client.actions == []


def test_filing_moves_every_stray_into_music(make_raindrop):
    a = make_raindrop(link=ALBUM, collection_id=UNSORTED)
    b = make_raindrop(link=OTHER, collection_id=UNSORTED)
    client = RecordingClient()
    apply_filing(client, build_plan([a, b]))
    assert client.actions == [("move", (a.id, b.id), MUSIC_COLLECTION)]


def test_a_drifted_date_tag_is_held_back_and_surfaced(make_raindrop):
    """The date format changed once already. If it changes again, the run must
    say so rather than stamping a survivor with a date it never had."""
    old = make_raindrop(link=ALBUM, tags=("music",), created="2025-01-01T00:00:00.000Z")
    new = make_raindrop(
        link=ALBUM, tags=("2026-08-27", "to-read"), created="2025-06-01T00:00:00.000Z"
    )
    plan = build_plan([old, new])
    assert plan.held_back_tags == ("2026-08-27",)
    [group] = plan.groups
    assert "2026-08-27" not in group.merged_tags
    assert "to-read" in group.merged_tags


def test_an_empty_plan_writes_nothing(make_raindrop):
    filed = make_raindrop(link=ALBUM, collection_id=MUSIC_COLLECTION)
    client = RecordingClient()
    plan = build_plan([filed])
    apply_dedupe(client, plan)
    apply_filing(client, plan)
    assert client.actions == []


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

    console = Console(width=80, record=True)
    console.print(summary(build_plan([old, new, stray])))
    rendered = console.export_text()

    for label in (
        "duplicate groups",
        "raindrops to delete",
        "survivors gaining tags",
        "survivors to file",
        "stray links to file",
    ):
        assert label in rendered


def test_the_summary_of_an_empty_plan_is_all_zeroes(make_raindrop):
    console = Console(width=80, record=True)
    console.print(summary(build_plan([make_raindrop(collection_id=MUSIC_COLLECTION)])))
    rendered = console.export_text()
    assert "1" not in rendered


def test_fuzzy_preview_is_none_without_a_fuzzy_group(make_raindrop):
    old = make_raindrop(link=ALBUM, created="2025-01-01T00:00:00.000Z")
    new = make_raindrop(link=ALBUM, created="2025-02-01T00:00:00.000Z")
    assert fuzzy_preview(build_plan([old, new])) is None


def test_a_fuzzy_match_is_shown_before_the_confirm(make_raindrop, monkeypatch):
    bandcamp = make_raindrop(
        link="https://hektttt.bandcamp.com/album/forever",
        title="Forever | Hekt",
        collection_id=MUSIC_COLLECTION,
    )
    boomkat = make_raindrop(
        link="https://boomkat.com/products/forever-hekt",
        title="Hekt - Forever - Boomkat",
        collection_id=MUSIC_COLLECTION,
    )
    client = FakeClient([bandcamp, boomkat])

    result = invoke(monkeypatch, client, "--dry-run")

    assert "matched by title" in result.stdout
    assert "Hekt" in result.stdout
    assert "Forever" in result.stdout


def test_no_fuzzy_block_when_every_group_is_exact(make_raindrop, monkeypatch):
    old = make_raindrop(link=ALBUM, collection_id=UNSORTED, created="2025-01-01T00:00:00.000Z")
    new = make_raindrop(link=ALBUM, collection_id=UNSORTED, created="2025-06-01T00:00:00.000Z")
    client = FakeClient([old, new])

    result = invoke(monkeypatch, client, "--dry-run")

    assert "matched by title" not in result.stdout


class FakeClient:
    """Stands in for RaindropClient at the command level: a canned read and
    recorded writes, with an optional failure partway through a write."""

    def __init__(self, raindrops=(), fail_on=None):
        self._raindrops = list(raindrops)
        self._fail_on = fail_on
        self.actions = []

    def all_raindrops(self):
        return self._raindrops

    def set_tags(self, raindrop_id, tags):
        self._fail_if("set_tags")
        self.actions.append(("retag", raindrop_id, tuple(tags)))

    def move(self, ids, collection_id):
        if not ids:
            return
        self._fail_if("move")
        self.actions.append(("move", tuple(ids), collection_id))

    def delete(self, ids):
        if not ids:
            return
        self._fail_if("delete")
        self.actions.append(("delete", tuple(ids)))

    def _fail_if(self, name):
        if self._fail_on == name:
            raise RaindropError(f"boom during {name}")


def invoke(monkeypatch, client, *args, input=None):
    """Run the real `dedupe` command through the CLI, with `load_token` and
    `RaindropClient` swapped for a fake so nothing touches the network. A wide
    terminal keeps assertions from being defeated by Rich wrapping."""
    monkeypatch.setattr(dedupe_module, "load_token", lambda: "tok")
    monkeypatch.setattr(dedupe_module, "RaindropClient", lambda token: client)
    return CliRunner().invoke(
        app, ["raindrop", "dedupe", *args], input=input, env={"COLUMNS": "200"}
    )


def test_dry_run_prints_the_plan_and_writes_nothing(make_raindrop, monkeypatch):
    old = make_raindrop(link=ALBUM, collection_id=UNSORTED, created="2025-01-01T00:00:00.000Z")
    new = make_raindrop(link=ALBUM, collection_id=UNSORTED, created="2025-06-01T00:00:00.000Z")
    stray = make_raindrop(link=OTHER, collection_id=UNSORTED)
    client = FakeClient([old, new, stray])

    result = invoke(monkeypatch, client, "--dry-run")

    assert result.exit_code == 0
    assert "duplicate groups" in result.stdout
    assert "dry run: nothing written" in result.stdout
    assert client.actions == []


def test_the_command_surfaces_a_drifted_date_tag(make_raindrop, monkeypatch):
    """This must fail if the yellow print in `dedupe()` is ever deleted — that
    is the whole point of testing at the command level rather than just
    `build_plan`."""
    old = make_raindrop(link=ALBUM, tags=("music",), created="2025-01-01T00:00:00.000Z")
    new = make_raindrop(
        link=ALBUM, tags=("2026-08-27", "to-read"), created="2025-06-01T00:00:00.000Z"
    )
    client = FakeClient([old, new])

    result = invoke(monkeypatch, client, "--dry-run")

    assert "held back" in result.stdout
    assert "2026-08-27" in result.stdout


def test_a_missing_token_exits_cleanly_with_a_message(monkeypatch):
    def raise_missing():
        raise MissingToken("no token at ~/.config/raindrop/token")

    monkeypatch.setattr(dedupe_module, "load_token", raise_missing)

    result = CliRunner().invoke(app, ["raindrop", "dedupe"])

    assert result.exit_code != 0
    assert "no token" in result.stdout
    assert "Traceback" not in result.stdout


def test_a_read_failure_exits_cleanly_with_a_message(monkeypatch):
    class FailingReadClient(FakeClient):
        def all_raindrops(self):
            raise RaindropError("Raindrop returned 500 for GET /raindrops/0")

    result = invoke(monkeypatch, FailingReadClient())

    assert result.exit_code != 0
    assert "Raindrop returned 500" in result.stdout
    assert "Traceback" not in result.stdout


def test_a_write_failure_exits_cleanly_with_no_traceback(make_raindrop, monkeypatch):
    old = make_raindrop(link=ALBUM, collection_id=UNSORTED, created="2025-01-01T00:00:00.000Z")
    new = make_raindrop(link=ALBUM, collection_id=UNSORTED, created="2025-06-01T00:00:00.000Z")
    client = FakeClient([old, new], fail_on="move")

    result = invoke(monkeypatch, client, input="y\n")

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert not isinstance(result.exception, RaindropError)


def test_declining_the_delete_prompt_still_offers_filing(make_raindrop, monkeypatch):
    old = make_raindrop(link=ALBUM, collection_id=UNSORTED, created="2025-01-01T00:00:00.000Z")
    new = make_raindrop(link=ALBUM, collection_id=UNSORTED, created="2025-06-01T00:00:00.000Z")
    stray = make_raindrop(link=OTHER, collection_id=UNSORTED)
    client = FakeClient([old, new, stray])

    result = invoke(monkeypatch, client, input="n\ny\n")

    assert result.exit_code == 0
    assert client.actions == [("move", (stray.id,), MUSIC_COLLECTION)]
    assert "duplicates left alone" in result.stdout
    assert "strays filed" in result.stdout


def test_the_plan_holds_against_the_real_account():
    """The numbers the design was argued from. If a change moves any of these,
    it should be because the rules changed, not by accident.

    Regenerate the fixture and update these numbers when the account itself
    has moved on.
    """
    raindrops = [to_raindrop(item) for item in json.loads(FIXTURE.read_text())]
    plan = build_plan(raindrops)
    assert len(plan.groups) == 152
    assert len(plan.deletions) == 155
    assert len(plan.retags) == 1
    assert len(plan.survivor_moves) == 74
    assert len(plan.stray_moves) == 575


def test_nothing_is_both_deleted_and_moved():
    """A raindrop appearing in two lists would mean writing to something that
    is about to go to Trash."""
    raindrops = [to_raindrop(item) for item in json.loads(FIXTURE.read_text())]
    plan = build_plan(raindrops)
    moved = set(plan.survivor_moves) | set(plan.stray_moves)
    assert not moved & set(plan.deletions)


def test_no_non_music_link_is_touched():
    """The blast radius: every id the plan writes to must be a music link.

    The rule is restated here rather than imported from `plan.is_music`. A test
    that asks the implementation what the answer should be cannot catch the
    implementation being wrong — it moves in lockstep with whatever `is_music`
    happens to do today.
    """
    raindrops = [to_raindrop(item) for item in json.loads(FIXTURE.read_text())]
    plan = build_plan(raindrops)

    # Tagged `music`, or filed in the music collection. Written out, not imported.
    music_ids = {
        r.id for r in raindrops if "music" in r.tags or r.collection_id == MUSIC_COLLECTION
    }
    touched = (
        set(plan.deletions)
        | set(plan.survivor_moves)
        | set(plan.stray_moves)
        | {rid for rid, _ in plan.retags}
    )
    assert touched <= music_ids
