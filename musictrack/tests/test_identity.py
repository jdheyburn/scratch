"""Two links are the same bookmark when their normalised URLs match."""

import pytest

from musictrack.identity import normalise

BLEEP = "https://bleep.com/release/53848-aphex-twin-syro"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        # The rule that does the work: bleep.com sends the same release with
        # and without its tracking param.
        (f"{BLEEP}?_kx=TjgIXRdL4U--dJDSZ4fu1HmcV7tSH36oym2g04zva5c.Wkkzk5", BLEEP),
        (BLEEP, BLEEP),
        # Insurance against sources that behave differently.
        ("http://bleep.com/release/53848-aphex-twin-syro", BLEEP),
        ("https://www.bleep.com/release/53848-aphex-twin-syro", BLEEP),
        ("https://BLEEP.com/release/53848-aphex-twin-syro", BLEEP),
        (f"{BLEEP}/", BLEEP),
        (f"{BLEEP}#tracklist", BLEEP),
        (f"{BLEEP}?utm_source=newsletter", BLEEP),
        (f"{BLEEP}?fbclid=abc", BLEEP),
        (f"{BLEEP}?gclid=abc", BLEEP),
        (f"{BLEEP}?ref=email", BLEEP),
        (f"{BLEEP}?referrer=email", BLEEP),
    ],
)
def test_noise_is_stripped(url, expected):
    assert normalise(url) == expected


def test_meaningful_query_params_survive():
    """phonicarecords puts the product id in the query string on some pages."""
    url = "https://phonicarecords.com/product?id=209166"
    assert normalise(url) == "https://phonicarecords.com/product?id=209166"


def test_bandcamps_referral_param_is_stripped():
    """`?from=fanpub_fb` is how Bandcamp tags a link shared from a fan page.
    One album in the account is saved both bare and with it."""
    album = "https://biodive.bandcamp.com/album/closed-circuit"
    assert normalise(f"{album}?from=fanpub_fb") == album


@pytest.mark.parametrize(
    "value", ["fanpub_fb", "fanpub_fnb", "fanpub_fnb_trk", "fanpub_fb_merch", "com-e-nm"]
)
def test_every_from_value_in_the_account_is_stripped(value):
    album = "https://example.bandcamp.com/album/x"
    assert normalise(f"{album}?from={value}") == album


def test_a_blank_valued_param_does_not_vanish():
    """parse_qsl drops blank values by default, which would make `?id=` and a
    bare URL the same bookmark — a false merge, and this tool deletes."""
    assert normalise("https://phonicarecords.com/product?id=") != normalise(
        "https://phonicarecords.com/product"
    )


@pytest.mark.parametrize("param", ["vgo_ee", "srsltid", "ml_subscriber", "sid", "st"])
def test_params_that_group_nothing_are_left_alone(param):
    """Measured against the real account: none of these join any two links, so
    stripping them would be risk without benefit."""
    url = f"https://bleep.com/release/1-x?{param}=abc"
    assert normalise(url) == url


def test_query_params_are_ordered_so_the_same_pair_matches():
    a = normalise("https://example.com/x?b=2&a=1")
    b = normalise("https://example.com/x?a=1&b=2")
    assert a == b


def test_different_releases_stay_different():
    assert normalise(BLEEP) != normalise("https://bleep.com/release/577458-yu-su-foundry")


def test_a_bare_domain_keeps_working():
    """The ssp.sh duplicate is a root URL with nothing to strip but the slash."""
    assert normalise("https://www.ssp.sh/") == "https://ssp.sh"
