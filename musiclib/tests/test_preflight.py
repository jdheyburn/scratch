import pytest

from musiclib.cover import Cover
from musiclib.preflight import preflight


def severities(findings):
    return [f.severity for f in findings]


def test_a_well_formed_album_produces_no_findings(make_candidate):
    assert preflight(make_candidate()) == []


def test_track_count_mismatch_stops_the_album_and_reports_both_counts(make_candidate):
    findings = preflight(make_candidate(flac_count=16))
    assert severities(findings) == ["stop"]
    assert "16" in findings[0].message and "9" in findings[0].message


@pytest.mark.parametrize(
    "cover, expected",
    [
        (None, ["stop"]),
        # beets' own fetchart minwidth is 500, so it would reject these anyway.
        (Cover(480, 480), ["stop"]),
        (Cover(499, 499), ["stop"]),
        (Cover(500, 500), ["warn"]),
        (Cover(999, 999), ["warn"]),
        # At or above the preferred width, nothing to say.
        (Cover(1000, 1000), []),
        (Cover(3000, 3000), []),
    ],
    ids=["absent", "480", "499", "500", "999", "1000", "3000"],
)
def test_cover_size_thresholds(make_candidate, cover, expected):
    assert severities(preflight(make_candidate(cover=cover))) == expected


def test_side_count_disagreeing_with_project_files_only_warns(make_candidate):
    findings = preflight(make_candidate(aup3_count=3))
    assert severities(findings) == ["warn"]
    assert "side" in findings[0].message.lower()


def test_no_side_check_when_the_release_has_no_lettered_positions(make_candidate, make_release):
    findings = preflight(make_candidate(release=make_release(tracks=9, sides=""), aup3_count=3))
    assert findings == []


def test_an_album_without_a_release_skips_track_and_side_checks(make_candidate):
    assert preflight(make_candidate(release=None, flac_count=16, aup3_count=3)) == []


def test_an_album_without_a_release_still_requires_a_cover(make_candidate):
    assert severities(preflight(make_candidate(release=None, cover=None))) == ["stop"]
