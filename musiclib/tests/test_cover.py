import io

import pytest
from PIL import Image

from musiclib.cover import prepare_cover
from musiclib.errors import BadCover


def is_jpeg(data):
    return data[:2] == b"\xff\xd8"


def test_reports_the_dimensions_of_the_image(make_image):
    cover, _ = prepare_cover(make_image("PNG", size=(1200, 1180)))
    assert (cover.width, cover.height) == (1200, 1180)


@pytest.mark.parametrize("fmt", ["PNG", "WEBP", "JPEG"])
def test_normalises_every_source_format_to_jpeg(make_image, fmt):
    """Your khruangbin cover is a WEBP named .jpg — players disagree about those."""
    _, data = prepare_cover(make_image(fmt))
    assert is_jpeg(data)


@pytest.mark.parametrize("mode", ["RGBA", "P", "LA"])
def test_flattens_modes_jpeg_cannot_represent(make_image, mode):
    _, data = prepare_cover(make_image("PNG", mode=mode))
    with Image.open(io.BytesIO(data)) as im:
        assert im.mode == "RGB"


def test_preserves_dimensions_through_conversion(make_image):
    cover, data = prepare_cover(make_image("WEBP", size=(3000, 3000)))
    assert cover.width == 3000
    with Image.open(io.BytesIO(data)) as im:
        assert im.size == (3000, 3000)


@pytest.mark.parametrize(
    "data",
    [b"<html>404 not found</html>", b"", b"\x89PNG\r\n\x1a\n truncated"],
    ids=["html-error-page", "empty", "truncated-png"],
)
def test_rejects_anything_that_is_not_a_usable_image(data):
    with pytest.raises(BadCover):
        prepare_cover(data)
