"""Album identity. Every case here is a real string from the 2026-09-03 capture."""

import pytest

from musictrack.albumkey import agree, artists, key, loose


@pytest.mark.parametrize(
    "left, right",
    [
        ("Arseholes, Liars, and Electronic Pioneers", "Arseholes, Liars, And Electronic Pioneers"),
        ("zakè", "zake"),
        ("Virtual Dreams: Ambient Explorations", "Virtual Dreams (Ambient Explorations)"),
        ("You're the One for Me", "You're The One For Me"),
    ],
)
def test_the_exact_tier_ignores_case_punctuation_and_accents(left, right):
    assert key(left) == key(right)


@pytest.mark.parametrize(
    "title, expected",
    [
        ("Pitstop Box LP", "pitstop box"),
        ("ITLP09 - Pool", "pool"),
        ("AI-16: Bioluminescence", "bioluminescence"),
        ("Landmarks (Remastered)", "landmarks"),
        (
            "The Hilvarenbeek Recordings [Remastered and expanded version]",
            "hilvarenbeek recordings",
        ),
        ("Information (Redacted)", "information"),
    ],
)
def test_the_loose_tier_strips_catalogue_numbers_editions_and_format_suffixes(title, expected):
    assert loose(title) == expected


def test_the_exact_tier_keeps_what_the_loose_tier_strips():
    """Sault's three Untitled albums must not collapse into one."""
    assert key("Untitled (Black Is)") != key("Untitled (Rise)")


@pytest.mark.parametrize(
    "left, right",
    [
        ("36", "36 & zakè"),
        ("Celer + Forest Management", "Celer, Forest Management"),
        ("Joachim Spieth | Andrew Thomas", "Andrew Thomas"),
        ("Benoît Pioulard • Hotel Neon • Viul", "Hotel Neon"),
        ("Various", "Various Artists"),
    ],
)
def test_artists_agree_across_every_separator_the_sources_use(left, right):
    assert agree(artists(left), artists(right))


@pytest.mark.parametrize(
    "left, right",
    [
        ("Bok Bok", "Aly-Us, Classic Man, Suges"),
        ("Various Artists", "Theo Parrish"),
        ("The Bug", "Lethal Bizzle"),
    ],
)
def test_unrelated_artists_do_not_agree(left, right):
    assert not agree(artists(left), artists(right))


def test_two_compilations_agree_only_with_each_other():
    """Otherwise every compilation matches every other compilation."""
    assert artists("Various Artists").various
    assert not artists("Theo Parrish").various
