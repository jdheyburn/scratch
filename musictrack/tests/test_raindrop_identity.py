"""Per-domain title parsing: real page-title shapes, and the near-misses that
correctly return nothing."""

# ruff: noqa: RUF001
import pytest

from musictrack.models import Raindrop
from musictrack.raindrop_identity import is_bandcamp, parse_release


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
