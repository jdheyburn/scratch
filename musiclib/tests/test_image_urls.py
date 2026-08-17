import pytest

from musiclib.cover import upgrade_image_url


@pytest.mark.parametrize(
    "url, expected",
    [
        # Bandcamp encodes the size in the filename suffix: _16 is 700px,
        # _10 is 1200px, _0 is the original upload.
        (
            "https://f4.bcbits.com/img/a3990828446_16.jpg",
            "https://f4.bcbits.com/img/a3990828446_0.jpg",
        ),
        (
            "https://f4.bcbits.com/img/a3852741963_10.jpg",
            "https://f4.bcbits.com/img/a3852741963_0.jpg",
        ),
        (
            "https://f4.bcbits.com/img/a123_7.jpg",
            "https://f4.bcbits.com/img/a123_0.jpg",
        ),
    ],
    ids=["700px", "1200px", "small"],
)
def test_asks_bandcamp_for_the_original_upload(url, expected):
    assert upgrade_image_url(url) == expected


def test_leaves_an_already_original_bandcamp_url_alone():
    url = "https://f4.bcbits.com/img/a3990828446_0.jpg"
    assert upgrade_image_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "https://i.discogs.com/abc/h:600/w:600/image_16.jpeg",
        "https://example.com/art_16.jpg",
        "https://f4.bcbits.com/img/coverart.jpg",
        "",
    ],
    ids=["discogs", "other-host", "no-suffix", "empty"],
)
def test_leaves_everything_that_is_not_a_bandcamp_size_suffix_alone(url):
    assert upgrade_image_url(url) == url
