"""Date tags record when a batch was saved, so they must never travel."""

import pytest

from musictrack.tags import (
    held_back,
    is_date_tag,
    looks_like_an_unknown_date,
    merge_tags,
)

# Every date format found on the account, both styles.
DATE_TAGS = [
    "12/07/2026",
    "27/07/2025",
    "01/02/2026",
    "09/08/2026",
    "5/4/2026",
    "June 25 2024",
    "December 12 2024",
    "September 14 2023",
    "March 3 2025",
    "December 3, 2023",
]

# Every real tag on the account. None of these may be mistaken for a date.
REAL_TAGS = [
    "music",
    "to-read",
    "onetab",
    "tab-cleardown",
    "boardgames",
    "glasses",
    "obsidian",
    "career",
    "personal growth",
    "streaming",
    "aggregator",
    "annotations",
    "architecture",
    "cloud",
    "consulting",
    "daily notes",
    "datadog",
    "example",
    "homelab",
    "incidents",
    "internal-development-platform",
    "link-aggregator",
    "pkm",
    "tech",
    "writing",
]


@pytest.mark.parametrize("tag", DATE_TAGS)
def test_date_tags_are_recognised(tag):
    assert is_date_tag(tag)


@pytest.mark.parametrize("tag", REAL_TAGS)
def test_real_tags_are_not_dates(tag):
    assert not is_date_tag(tag)


def test_the_survivor_gains_real_tags_from_an_extra():
    """The `randomer` group: the oldest copy has no tags at all, and the merge
    is the only thing that saves them."""
    merged = merge_tags([], [["December 16 2024", "to-read", "music"]])
    assert merged == ("music", "to-read")


def test_date_tags_are_never_merged_in():
    merged = merge_tags(["12/07/2026", "music", "to-read"], [["12/08/2026", "music", "to-read"]])
    assert merged == ("12/07/2026", "music", "to-read")


def test_the_survivors_own_date_tag_is_kept():
    """We drop dates coming *from extras*, not the survivor's own history."""
    merged = merge_tags(["June 25 2024"], [["music"]])
    assert merged == ("June 25 2024", "music")


def test_merging_is_stable_and_deduplicated():
    merged = merge_tags(["music"], [["music"], ["music", "to-read"], ["to-read"]])
    assert merged == ("music", "to-read")


def test_no_extras_leaves_the_survivor_alone():
    assert merge_tags(["music", "to-read"], []) == ("music", "to-read")


# The two known formats are disjoint eras — `June 25 2024` ran to 2025-03,
# `12/07/2026` from 2025-04. A third era would otherwise merge silently.


@pytest.mark.parametrize(
    "tag",
    [
        "2026-08-27",  # ISO, the obvious next format
        "27 August 2026",  # day-first long form
        "12/07/26",  # two-digit year
        "Aug 27, 2026",  # abbreviated month
        "saved 2026",
    ],
)
def test_an_unrecognised_date_shape_is_noticed(tag):
    assert looks_like_an_unknown_date(tag)


@pytest.mark.parametrize("tag", REAL_TAGS)
def test_real_tags_are_not_mistaken_for_unknown_dates(tag):
    assert not looks_like_an_unknown_date(tag)


@pytest.mark.parametrize("tag", DATE_TAGS)
def test_a_known_date_is_not_also_an_unknown_one(tag):
    """The two predicates must not both fire, or a known stamp gets reported."""
    assert not looks_like_an_unknown_date(tag)


def test_an_unrecognised_date_is_not_merged_onto_the_survivor():
    """The corruption this guards against: stamping a bookmark with a date it
    was never saved on."""
    assert merge_tags(["music"], [["2026-08-27", "to-read"]]) == ("music", "to-read")


def test_what_was_held_back_is_reported():
    assert held_back([["2026-08-27", "to-read"], ["saved 2026"]]) == (
        "2026-08-27",
        "saved 2026",
    )


def test_nothing_is_held_back_on_the_accounts_current_tags():
    """Zero tags on the account trip this today; it stays silent until the
    format actually drifts."""
    assert held_back([DATE_TAGS, REAL_TAGS]) == ()
