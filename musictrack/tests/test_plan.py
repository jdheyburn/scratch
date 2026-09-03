"""What the tool intends to do, worked out before anything is written."""

from musictrack.plan import MUSIC_COLLECTION, UNSORTED, build_plan, is_music

ALBUM = "https://homenormal.bandcamp.com/album/pola"
OTHER = "https://stroomtv.bandcamp.com/album/other"


def test_a_link_tagged_music_counts(make_raindrop):
    assert is_music(make_raindrop(tags=("music",), collection_id=UNSORTED))


def test_a_link_filed_in_music_counts_even_untagged(make_raindrop):
    """Two raindrops sit in the music collection without the tag."""
    assert is_music(make_raindrop(tags=(), collection_id=MUSIC_COLLECTION))


def test_a_tech_link_does_not_count(make_raindrop):
    assert not is_music(make_raindrop(tags=("tech",), collection_id=29207216))


def test_non_music_links_are_ignored_entirely(make_raindrop):
    """A duplicated tech bookmark must survive untouched."""
    dupes = [
        make_raindrop(link="https://ssp.sh", tags=("tech",), collection_id=29207216),
        make_raindrop(link="https://ssp.sh", tags=("tech",), collection_id=29207268),
    ]
    plan = build_plan(dupes)
    assert plan.groups == ()
    assert plan.deletions == ()


def test_the_oldest_survives(make_raindrop):
    old = make_raindrop(link=ALBUM, created="2025-09-20T00:00:00.000Z")
    new = make_raindrop(link=ALBUM, created="2025-10-12T00:00:00.000Z")
    plan = build_plan([new, old])
    [group] = plan.groups
    assert group.survivor.id == old.id
    assert plan.deletions == (new.id,)


def test_links_differing_only_by_tracking_param_are_one_group(make_raindrop):
    bare = make_raindrop(
        link="https://bleep.com/release/53848-aphex-twin-syro",
        created="2025-01-01T00:00:00.000Z",
    )
    tracked = make_raindrop(
        link="https://bleep.com/release/53848-aphex-twin-syro?_kx=abc",
        created="2025-06-01T00:00:00.000Z",
    )
    plan = build_plan([bare, tracked])
    [group] = plan.groups
    assert group.survivor.id == bare.id
    assert plan.deletions == (tracked.id,)


def test_a_unique_link_is_not_a_group(make_raindrop):
    plan = build_plan([make_raindrop(link=ALBUM), make_raindrop(link=OTHER)])
    assert plan.groups == ()


def test_a_survivor_in_unsorted_is_moved(make_raindrop):
    """The common shape: the older copy is stranded in Unsorted while the
    newer one was filed."""
    old = make_raindrop(link=ALBUM, collection_id=UNSORTED, created="2025-09-20T00:00:00.000Z")
    new = make_raindrop(
        link=ALBUM, collection_id=MUSIC_COLLECTION, created="2025-10-12T00:00:00.000Z"
    )
    plan = build_plan([old, new])
    assert plan.survivor_moves == (old.id,)
    assert plan.deletions == (new.id,)


def test_a_survivor_already_filed_is_left_where_it_is(make_raindrop):
    """The ssp.sh shape, but for music: the survivor sits in a real collection
    that isn't `music`, and we do not adjudicate between two real collections."""
    old = make_raindrop(link=ALBUM, collection_id=29207268, created="2024-12-12T00:00:00.000Z")
    new = make_raindrop(
        link=ALBUM, collection_id=MUSIC_COLLECTION, created="2024-12-13T00:00:00.000Z"
    )
    plan = build_plan([old, new])
    assert plan.survivor_moves == ()
    assert plan.deletions == (new.id,)


def test_a_survivor_gains_the_extras_real_tags(make_raindrop):
    """The `randomer` group: the oldest copy carries no tags at all."""
    old = make_raindrop(link=ALBUM, tags=(), created="2024-12-16T00:00:00.000Z")
    new = make_raindrop(
        link=ALBUM,
        tags=("December 16 2024", "to-read", "music"),
        created="2024-12-16T12:00:00.000Z",
    )
    plan = build_plan([old, new])
    assert plan.retags == ((old.id, ("music", "to-read")),)


def test_no_retag_when_the_survivor_already_has_every_real_tag(make_raindrop):
    """The overwhelmingly common case. Writing here would be a wasted request."""
    old = make_raindrop(link=ALBUM, tags=("12/07/2026", "music", "to-read"))
    new = make_raindrop(
        link=ALBUM, tags=("12/08/2026", "music", "to-read"), created="2026-08-12T00:00:00.000Z"
    )
    plan = build_plan([old, new])
    assert plan.retags == ()


def test_strays_are_music_links_in_unsorted_that_are_not_duplicates(make_raindrop):
    stray = make_raindrop(link=OTHER, collection_id=UNSORTED)
    filed = make_raindrop(link=ALBUM, collection_id=MUSIC_COLLECTION)
    plan = build_plan([stray, filed])
    assert plan.stray_moves == (stray.id,)


def test_a_deleted_extra_is_never_also_a_stray(make_raindrop):
    """An extra bound for the trash must not be queued for a move as well."""
    old = make_raindrop(
        link=ALBUM, collection_id=MUSIC_COLLECTION, created="2025-01-01T00:00:00.000Z"
    )
    new = make_raindrop(link=ALBUM, collection_id=UNSORTED, created="2025-06-01T00:00:00.000Z")
    plan = build_plan([old, new])
    assert plan.deletions == (new.id,)
    assert plan.stray_moves == ()


def test_a_survivor_being_moved_is_not_also_a_stray(make_raindrop):
    old = make_raindrop(link=ALBUM, collection_id=UNSORTED, created="2025-01-01T00:00:00.000Z")
    new = make_raindrop(link=ALBUM, collection_id=UNSORTED, created="2025-06-01T00:00:00.000Z")
    plan = build_plan([old, new])
    assert plan.survivor_moves == (old.id,)
    assert plan.stray_moves == ()


def test_three_copies_leave_one(make_raindrop):
    a = make_raindrop(link=ALBUM, created="2025-01-01T00:00:00.000Z")
    b = make_raindrop(link=ALBUM, created="2025-02-01T00:00:00.000Z")
    c = make_raindrop(link=ALBUM, created="2025-03-01T00:00:00.000Z")
    plan = build_plan([c, a, b])
    [group] = plan.groups
    assert group.survivor.id == a.id
    assert set(plan.deletions) == {b.id, c.id}


def test_the_plan_is_deterministic(make_raindrop):
    """Same input in any order, same plan out — so the table you approve is
    the plan that runs."""
    drops = [
        make_raindrop(link=ALBUM, id=1, created="2025-01-01T00:00:00.000Z"),
        make_raindrop(link=ALBUM, id=2, created="2025-02-01T00:00:00.000Z"),
        make_raindrop(link=OTHER, id=3, collection_id=UNSORTED),
    ]
    assert build_plan(drops) == build_plan(list(reversed(drops)))


def test_the_same_raindrop_twice_is_never_deleted_as_its_own_duplicate(make_raindrop):
    """A read whose pages overlap can hand the same record over twice. Both
    copies normalise to one URL, so without this the plan would group the
    raindrop with itself and send one of them to Trash. There is only one
    raindrop, so that is the raindrop. The client dedupes as it pages; this is
    the same rule held one layer down, where it costs a dict.

    `test_nothing_is_both_deleted_and_moved` checks the same invariant against
    the fixture, but every id there is distinct, so this case never runs.
    """
    drop = make_raindrop(link=ALBUM, id=42, collection_id=UNSORTED)
    plan = build_plan([drop, drop])
    assert plan.groups == ()
    assert plan.deletions == ()
    assert plan.survivor_moves == ()
    assert not set(plan.deletions) & set(plan.survivor_moves)
    # The one real copy is still a stray in Unsorted, and still gets filed.
    assert plan.stray_moves == (42,)
