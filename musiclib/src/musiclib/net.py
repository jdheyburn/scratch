"""The one place that touches the network.

Every caller takes a `get=http_get` parameter, so tests inject a transport and
nothing in the suite reaches the internet.
"""

from __future__ import annotations

import requests

# Discogs asks that API clients identify themselves descriptively.
USER_AGENT = "musiclib/0.1 +https://github.com/jdheyburn"
# Shop and label CDNs (cloudfront and friends) answer 403 to anything that
# doesn't look like a browser, so artwork is fetched as one.
IMAGE_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def http_get(url: str, headers: dict | None = None) -> bytes:
    """Default transport. Injected in tests so nothing here hits the network."""
    response = requests.get(url, headers=headers or {}, timeout=20)
    response.raise_for_status()
    return response.content
