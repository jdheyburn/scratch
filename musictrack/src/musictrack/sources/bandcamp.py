"""The only module that talks to Bandcamp.

There is no published API. These endpoints are the ones the website calls, and
they authenticate with the browser's own cookie jar. The `identity` cookie on
its own is not enough: Bandcamp answers it with HTTP 200 and an empty
`identities`, which is a successful-looking way of saying you are logged out.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

import requests

from musictrack.errors import BandcampError
from musictrack.models import AlbumRef

API = "https://bandcamp.com"

# Bandcamp serves the API to browsers. Without a browser User-Agent the cookie
# jar is not enough.
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:131.0) Gecko/20100101 Firefox/131.0"

PAGE_SIZE = 100
PAUSE_SECONDS = 1.0

# The cursor cycles rather than ending, so the real stop conditions are "no new
# items" and "the token repeated". This only bounds a source that does neither.
MAX_PAGES = 60

Transport = Callable[..., dict]

EXPIRED = (
    "Bandcamp answered as a logged-out visitor. The cookie jar has expired.\n"
    "Log in at bandcamp.com in Firefox and copy the jar again."
)


def http_request(method: str, url: str, cookie: str, payload: dict | None = None) -> dict:
    """Default transport. Injected in tests so nothing here hits the network."""
    try:
        response = requests.request(
            method,
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Cookie": cookie,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
    except requests.RequestException as exc:
        raise BandcampError(f"could not reach Bandcamp for {method} {url}: {exc}") from exc
    if response.status_code >= 400:
        raise BandcampError(f"Bandcamp returned {response.status_code} for {method} {url}")
    try:
        return response.json()
    except ValueError as exc:
        raise BandcampError(f"Bandcamp sent a body {method} {url} could not decode") from exc


@dataclass(frozen=True)
class Summary:
    """What the account says it holds, before anything is paged."""

    fan_id: int
    purchased: int
    wishlisted: int


def to_ref(item: dict, source: str) -> AlbumRef:
    return AlbumRef(
        source=source,
        artist=item.get("band_name") or "",
        album=item.get("item_title") or "",
        ref=str(item.get("item_id")),
        url=item.get("item_url") or "",
    )


class BandcampClient:
    """Reads one fan account. Writes nothing."""

    def __init__(
        self,
        cookie: str,
        request: Transport = http_request,
        pause: float = PAUSE_SECONDS,
    ) -> None:
        self._cookie = cookie
        self._request = request
        self._pause = pause

    def summary(self) -> Summary:
        """Who we are, and how much there is to read.

        `tralbum_lookup` holds the collection and the wishlist together, and
        `purchased` is true for exactly the collection.
        """
        body = self._request("GET", f"{API}/api/fan/2/collection_summary", self._cookie)
        fan_id = body.get("fan_id")
        if not fan_id:
            raise BandcampError(EXPIRED)
        lookup = (body.get("collection_summary") or {}).get("tralbum_lookup") or {}
        purchased = sum(1 for entry in lookup.values() if entry.get("purchased"))
        return Summary(int(fan_id), purchased, len(lookup) - purchased)

    def collection(self) -> list[AlbumRef]:
        """Everything bought."""
        found = self.summary()
        return [
            to_ref(item, "bandcamp-collection")
            for item in self._items("collection_items", found.fan_id, found.purchased)
        ]

    def wishlist(self) -> list[AlbumRef]:
        """Everything wished for."""
        found = self.summary()
        return [
            to_ref(item, "bandcamp-wishlist")
            for item in self._items("wishlist_items", found.fan_id, found.wishlisted)
        ]

    def _items(self, kind: str, fan_id: int, expected: int) -> list[dict]:
        """Page until the cursor stops producing anything new.

        `more_available` cannot be trusted to end the loop: the collection
        cursor returns to an earlier token after about four pages and keeps
        claiming there is more, serving the same items indefinitely.
        """
        found: list[dict] = []
        seen: set[int] = set()
        token = f"{int(time.time())}::a::"
        for page in range(MAX_PAGES):
            if page:
                time.sleep(self._pause)
            body = self._request(
                "POST",
                f"{API}/api/fancollection/1/{kind}",
                self._cookie,
                {"fan_id": fan_id, "older_than_token": token, "count": PAGE_SIZE},
            )
            items = body.get("items") or []
            if not items:
                break
            fresh = [item for item in items if item.get("item_id") not in seen]
            for item in fresh:
                seen.add(item["item_id"])
                found.append(item)
            if not fresh:
                break
            following = items[-1].get("token") or body.get("last_token")
            if not following or following == token:
                break
            token = following
            if not body.get("more_available"):
                break
        else:
            raise BandcampError(f"stopped after {MAX_PAGES} pages of {kind}")
        if len(found) < expected:
            raise BandcampError(
                f"read {len(found)} of {expected} {kind}; the paged read lost records"
            )
        return found
