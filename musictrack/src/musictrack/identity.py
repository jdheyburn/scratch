"""What makes two bookmarks the same bookmark.

Only one of these rules earns its keep on the current data: dropping tracking
params. Exact matching and case/slash normalisation both find 95 duplicate
groups; dropping tracking params takes it to 100. The rest stay as cheap
insurance against sources that behave differently.

Two params account for the gain. `_kx` is bleep.com's and brings 4 groups.
`from` is Bandcamp's referral code and brings 1 — an album saved bare and again
as `?from=fanpub_fb`. Params measured and deliberately NOT stripped, because
they group nothing: `vgo_ee` (29 occurrences), `srsltid`, `ml_subscriber`.
Every name added here is a chance to merge two pages that genuinely differ, so
the list stays at what the data justifies.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Newsletter and ad-network noise. `_kx` is bleep.com's, `from` is Bandcamp's;
# the rest are the usual suspects. Anchored at both ends so a real param called
# `reference` isn't caught by `ref`.
TRACKING_PARAM = re.compile(r"^(utm_[a-z_]*|fbclid|gclid|_kx|ref|referrer|from)$", re.IGNORECASE)


def normalise(url: str) -> str:
    """The comparable form of a URL: same page in, same string out."""
    parts = urlsplit(url)
    host = parts.netloc.lower().removeprefix("www.")
    path = parts.path.rstrip("/")
    # keep_blank_values, or `?id=` normalises to the same string as no query at
    # all and two different pages silently become one bookmark.
    query = sorted(
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not TRACKING_PARAM.match(k)
    )
    return urlunsplit(("https", host, path, urlencode(query), ""))
