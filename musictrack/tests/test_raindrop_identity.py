"""Per-domain title parsing: real page-title shapes, and the near-misses that
correctly return nothing."""

# ruff: noqa: RUF001
import pytest

from musictrack.models import Raindrop
from musictrack.raindrop_identity import group_by_release, is_bandcamp, parse_release


def raindrop(link: str, title: str) -> Raindrop:
    return Raindrop(
        id=1, link=link, title=title, tags=(), collection_id=1, created="2026-01-01T00:00:00.000Z"
    )


@pytest.mark.parametrize(
    ("link", "title", "expected"),
    [
        (
            "https://hektttt.bandcamp.com/album/forever",
            "Forever | Hekt",
            ("Hekt", "Forever"),
        ),
        (
            "https://nmbrs.bandcamp.com/album/main-character",
            "Main Character | Jubilee | Numbers",
            ("Jubilee", "Main Character"),
        ),
        (
            "https://boomkat.com/products/airdrop-ii",
            "Low End Activist - Airdrop II - Boomkat",
            ("Low End Activist", "Airdrop II"),
        ),
        (
            "https://boomkat.com/products/paired-works",
            "Justine Perry, Paula Koski - Paired Works - Boomkat",
            ("Justine Perry, Paula Koski", "Paired Works"),
        ),
        (
            "https://bleep.com/release/409678-mojave-3-out-of-tune",
            "Mojave 3 - Out of Tune. Bleep.",
            ("Mojave 3", "Out of Tune"),
        ),
        (
            "https://www.phonicarecords.com/product/view/211675",
            "DJ PLEAD/Please LP/SMALLTOWN SUPERSOUND - Vinyl Records Specialists, "
            "London Soho Vinyl Music Records - Phonica Records - Latest Releases, "
            "Pre-Orders and Merchandise",
            ("DJ PLEAD", "Please LP"),
        ),
        (
            "https://rubadub.co.uk/products/peace-portal",
            "Khotin - Peace Portal (Khotin Industries)",
            ("Khotin", "Peace Portal (Khotin Industries)"),
        ),
        (
            "https://rubadub.co.uk/products/faith-1",
            "Pre-Order: Purelink - Faith (Peak Oil)",
            ("Purelink", "Faith (Peak Oil)"),
        ),
        (
            "https://rubadub.co.uk/products/detwat",
            "Hi-Tech - DÉTWAT – Rubadub",
            ("Hi-Tech", "DÉTWAT"),
        ),
    ],
)
def test_a_release_page_title_parses_to_artist_and_album(link, title, expected):
    assert parse_release(raindrop(link, title)) == expected


@pytest.mark.parametrize(
    ("link", "title"),
    [
        ("https://someone.bandcamp.com/album/x", "The Best Ambient on Bandcamp: April 2023"),
        ("https://someone.bandcamp.com/album/x", "Biodive"),
        ("https://boomkat.com/products/charts", "Charts - Boomkat"),
        ("https://boomkat.com/products/self-titled", "Self Titled - Boomkat"),
        (
            "https://bleep.com/release/1-x",
            "Bleep - Your Source for Independent and Innovative Music - Buy Vinyl "
            "and CD, Download MP3, WAV/FLAC, 24bit WAV and Buy Merchandise",
        ),
        ("https://www.phonicarecords.com/x", "404 Page Not Found"),
        ("https://example.com/some/page", "An unrelated page"),
    ],
)
def test_a_page_that_is_not_a_release_parses_to_nothing(link, title):
    assert parse_release(raindrop(link, title)) is None


def test_a_bookmark_raindrop_never_fetched_a_title_for_parses_to_nothing():
    assert parse_release(raindrop("https://hektttt.bandcamp.com/album/forever", "")) is None


def test_html_entities_in_the_title_are_unescaped():
    found = parse_release(
        raindrop(
            "https://boomkat.com/products/queerifications-ruins",
            "DJ Sprinkles - Queerifications &amp; Ruins - Boomkat",
        )
    )
    assert found == ("DJ Sprinkles", "Queerifications & Ruins")


def test_bandcamp_is_recognised_regardless_of_subdomain():
    assert is_bandcamp(raindrop("https://hektttt.bandcamp.com/album/forever", "x"))
    assert not is_bandcamp(raindrop("https://boomkat.com/products/x", "x"))


def test_a_lookalike_domain_is_not_bandcamp():
    assert not is_bandcamp(raindrop("https://notbandcamp.com/album/x", "x"))


def test_bandcamp_daily_articles_do_not_parse_as_a_release():
    """`daily.bandcamp.com` is an article page, not a release page — every
    headline happens to share Bandcamp's `{Album} | {Artist}` release shape,
    which would parse every article as the same fake artist."""
    assert (
        parse_release(
            raindrop(
                "https://daily.bandcamp.com/best-of/some-headline",
                "Some Headline | Bandcamp Daily",
            )
        )
        is None
    )


def rd(id, link, title, created="2026-01-01T00:00:00.000Z"):
    return Raindrop(id=id, link=link, title=title, tags=(), collection_id=1, created=created)


def test_two_domains_with_the_same_release_cluster():
    bandcamp = rd(1, "https://hektttt.bandcamp.com/album/forever", "Forever | Hekt")
    boomkat = rd(2, "https://boomkat.com/products/forever-hekt", "Hekt - Forever - Boomkat")
    [cluster] = group_by_release([bandcamp, boomkat])
    assert cluster.matched_as == ("Hekt", "Forever")
    assert set(cluster.raindrops) == {bandcamp, boomkat}


def test_a_release_with_no_match_is_not_a_cluster():
    lone = rd(1, "https://hektttt.bandcamp.com/album/forever", "Forever | Hekt")
    assert group_by_release([lone]) == []


def test_the_same_loose_title_with_different_artists_does_not_cluster():
    one = rd(1, "https://a.bandcamp.com/album/untitled", "Untitled | Artist One")
    other = rd(2, "https://b.bandcamp.com/album/untitled", "Untitled | Artist Two")
    assert group_by_release([one, other]) == []


def test_a_shared_collaborator_is_enough_to_agree():
    """`agree()` needs only one shared name — the same rule `match.py` uses
    against beets applies here too."""
    one = rd(1, "https://a.bandcamp.com/album/split", "Split | Artist A, Artist B")
    other = rd(2, "https://boomkat.com/products/split", "Artist B - Split - Boomkat")
    [cluster] = group_by_release([one, other])
    assert set(cluster.raindrops) == {one, other}


def test_loose_matching_absorbs_a_format_or_label_tail():
    bandcamp = rd(1, "https://a.bandcamp.com/album/chapter-1", "Chapter 1 | SAULT")
    phonica = rd(
        2,
        "https://www.phonicarecords.com/product/view/1",
        "SAULT/Chapter 1 LP/Forever Living - Vinyl Records Specialists",
    )
    [cluster] = group_by_release([bandcamp, phonica])
    assert set(cluster.raindrops) == {bandcamp, phonica}


def test_a_raindrop_that_does_not_parse_is_never_in_a_cluster():
    bandcamp = rd(1, "https://a.bandcamp.com/album/x", "X | Artist")
    unparsed = rd(2, "https://a.bandcamp.com/album/x2", "An unrelated chart page")
    assert group_by_release([bandcamp, unparsed]) == []


def test_a_same_artist_release_distinguished_only_by_a_bracket_does_not_cluster():
    """`loose()` strips the trailing parenthetical from both titles down to
    the same base, but `(Part 1)` and `(Part 2)` name different records —
    same artist, same loose title, must not merge."""
    one = rd(1, "https://a.bandcamp.com/album/x", "White Line Sunrise III (Part 1) | Artist")
    other = rd(
        2,
        "https://boomkat.com/products/y",
        "Artist - White Line Sunrise III (Part 2) - Boomkat",
    )
    assert group_by_release([one, other]) == []
