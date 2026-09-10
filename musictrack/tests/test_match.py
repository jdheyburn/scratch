"""Verdicts. The library here is tiny; the rules are the same ones the real
2020-album library was measured against."""

import pytest

from musictrack.match import ABSENT, OWNED, POSSIBLE, LibraryIndex, variants
from musictrack.models import AlbumRef


def album(artist, title):
    return AlbumRef(source="beets", artist=artist, album=title, ref="")


def track(artist, title):
    return AlbumRef(source="beets-track", artist=artist, album=title, ref="")


def want(artist, title):
    return AlbumRef(source="bandcamp-wishlist", artist=artist, album=title, ref="1")


@pytest.fixture
def library():
    return LibraryIndex(
        albums=[
            album("Theo Parrish", "Parallel Dimensions"),
            album("Shinichiro Yokota", "Pitstop Box LP"),
            album("Aly-Us, Classic Man, Suges", "Hardbody Dubs, Vol. 4"),
            album("Various Artists", "Pop Ambient 2026"),
            album("Skee Mask", "Pool"),
            album("Blue Channel", "Dubplate Vibing Part I"),
            album("Aaliyah feat. Drake", ""),
        ],
        tracks=[track("Zorrovian", "BIOS")],
    )


def test_an_exact_title_with_an_agreeing_artist_is_owned(library):
    found = library.look_up(want("Theo Parrish", "Parallel Dimensions"))
    assert found.verdict == OWNED
    assert found.library is not None and found.library.album == "Parallel Dimensions"


def test_a_loose_only_hit_is_never_owned(library):
    """'Pitstop Box' vs 'Pitstop Box LP' is the same record, but the loose tier
    also merges records that differ, so it can only ever suggest."""
    assert library.look_up(want("Shinichiro Yokota", "Pitstop Box")).verdict == POSSIBLE


def test_a_title_hit_with_a_disagreeing_artist_needs_a_look(library):
    found = library.look_up(want("Bok Bok", "Hardbody Dubs Vol 4"))
    assert found.verdict == POSSIBLE


def test_a_singleton_track_counts_as_owned(library):
    """21 of 27 Bandcamp track purchases live in beets with no album at all."""
    assert library.look_up(want("Zorrovian", "BIOS")).verdict == OWNED


def test_the_artist_is_read_out_of_the_title_when_band_name_is_a_label(library):
    """Bandcamp files this under the label 'Kontakt Records'."""
    found = library.look_up(want("Kontakt Records", "Blue Channel - Dubplate Vibing Part I"))
    assert found.verdict == OWNED


def test_a_catalogue_number_prefix_still_finds_the_album(library):
    """The prefix survives the exact tier but not the loose one, so this is an
    album-loose hit: worth a look, never owned outright."""
    found = library.look_up(want("Skee Mask", "ITLP09 - Pool"))
    assert found.verdict == POSSIBLE
    assert found.tier == "album-loose"


def test_two_compilations_match_each_other(library):
    assert library.look_up(want("Various", "Pop Ambient 2026")).verdict == OWNED


def test_nothing_like_it_is_absent(library):
    assert library.look_up(want("Lucy Gooch", "Rushing")).verdict == ABSENT


def test_a_title_with_no_ascii_equivalent_never_matches_a_blank_library_title(library):
    """`_fold` drops anything with no ASCII equivalent, so a title written
    entirely in another script collapses to the same empty key as a genuinely
    blank library title. Empty is not a title either side owns."""
    assert library.look_up(want("Some Artist", "キャット")).verdict == ABSENT


def test_a_symbol_only_title_never_matches_a_blank_library_title(library):
    assert library.look_up(want("Some Artist", "( ͡° ͜ʖ ͡°)")).verdict == ABSENT


def test_variants_offers_the_label_reading_second():
    assert variants("Kontakt Records", "Blue Channel - Dubplate Vibing") == [
        ("Kontakt Records", "Blue Channel - Dubplate Vibing"),
        ("Blue Channel", "Dubplate Vibing"),
        ("Kontakt Records", "Dubplate Vibing"),
    ]


def test_variants_leaves_a_title_without_a_dash_alone():
    assert variants("Zorrovian", "BIOS") == [("Zorrovian", "BIOS")]
