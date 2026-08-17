"""Artwork: where to get it, how big it has to be, and what shape it lands in."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

from PIL import Image

from musiclib.errors import BadCover, DiscogsError
from musiclib.net import IMAGE_USER_AGENT, http_get

# beets' own fetchart minwidth — anything smaller is rejected at import anyway.
COVER_MIN_WIDTH = 500
# Below this we accept it but say so: your covers usually run 1000px and up.
COVER_PREFERRED_WIDTH = 1000

# Bandcamp encodes artwork size in the filename suffix; _0 is the original.
_BANDCAMP_ART = re.compile(r"^(https?://[^/]*\.bcbits\.com/img/[^/]+)_(\d+)(\.[a-z]+)$")


@dataclass(frozen=True)
class Cover:
    width: int
    height: int


def upgrade_image_url(url: str) -> str:
    """Ask Bandcamp for the original upload instead of a resized variant."""
    match = _BANDCAMP_ART.match(url)
    return f"{match[1]}_0{match[3]}" if match else url


def prepare_cover(data: bytes) -> tuple[Cover, bytes]:
    """Measure the artwork and normalise it to real JPEG.

    Sources hand back PNG and WEBP as often as JPEG, and a WEBP saved as
    `cover.jpg` renders in some players and not others.
    """
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.load()
            size = Cover(width=im.width, height=im.height)
            # JPEG has no alpha channel, so flatten anything that carries one.
            if im.mode not in ("RGB", "L"):
                im = im.convert("RGB")
            out = io.BytesIO()
            im.save(out, format="JPEG", quality=92, optimize=True)
    except BadCover:
        raise
    except Exception as e:
        raise BadCover(f"not a usable image: {e}") from None
    return size, out.getvalue()


def fetch_cover(url: str, get=http_get) -> tuple[Cover, bytes]:
    """Download the artwork you chose and normalise it to real JPEG."""
    try:
        data = get(
            url,
            {
                "User-Agent": IMAGE_USER_AGENT,
                "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
            },
        )
    except Exception as e:
        raise DiscogsError(f"could not fetch cover {url}: {e}") from None
    try:
        return prepare_cover(data)
    except BadCover as e:
        raise DiscogsError(f"cover at {url} is unusable: {e}") from None
