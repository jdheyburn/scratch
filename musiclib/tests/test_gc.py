from datetime import UTC, datetime, timedelta

import pytest

from musiclib.state import RETENTION_DAYS, expired_albums, update_state

NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)


def archived(days_ago):
    return (NOW - timedelta(days=days_ago)).isoformat()


@pytest.mark.parametrize(
    "days_ago, expected",
    [(0, False), (1, False), (20, False), (21, False), (22, True), (90, True)],
)
def test_only_albums_past_the_window_are_eligible(tmp_path, days_ago, expected):
    update_state(tmp_path, "daphni", archived_at=archived(days_ago))
    eligible = [slug for slug, _ in expired_albums(tmp_path, now=NOW)]
    assert ("daphni" in eligible) is expected


def test_an_album_that_was_never_archived_is_never_eligible(tmp_path):
    update_state(tmp_path, "daphni", synced_at=archived(90), imported_at=archived(90))
    assert expired_albums(tmp_path, now=NOW) == []


def test_the_window_is_configurable(tmp_path):
    update_state(tmp_path, "daphni", archived_at=archived(10))
    assert expired_albums(tmp_path, now=NOW, days=7) != []
    assert expired_albums(tmp_path, now=NOW, days=30) == []


def test_reports_how_long_ago_each_was_archived(tmp_path):
    update_state(tmp_path, "daphni", archived_at=archived(40))
    [(slug, age)] = expired_albums(tmp_path, now=NOW)
    assert slug == "daphni"
    assert age.days == 40


def test_the_default_window_is_three_weeks():
    assert RETENTION_DAYS == 21


def test_unreadable_timestamps_do_not_make_an_album_eligible(tmp_path):
    """Never delete on the strength of a date we couldn't parse."""
    update_state(tmp_path, "daphni", archived_at="not a date")
    assert expired_albums(tmp_path, now=NOW) == []
