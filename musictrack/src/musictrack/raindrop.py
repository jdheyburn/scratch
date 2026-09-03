"""The only module that talks to Raindrop.

`RaindropClient` takes a `request` transport, so tests inject a fake and
nothing in the suite reaches the internet.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from urllib.parse import urlencode

import requests

from musictrack.errors import RaindropError
from musictrack.models import Raindrop

API = "https://api.raindrop.io/rest/v1"

# The API caps a page at 50.
PAGE_SIZE = 50

# How many ids go in one batch write. The API documents no ceiling; 100 keeps
# request bodies small enough to reason about and errors small enough to read.
BATCH_SIZE = 100

# Collection 0 is "everything". Reading it is how the music links stranded in
# Unsorted are found; deleting against it moves raindrops to Trash. Collection
# -99 would delete permanently and is never used here.
ALL_COLLECTIONS = 0

# Oldest-first. The default order is creation-descending, so a raindrop saved
# while a 41-page read is in flight shifts every later page and one raindrop at
# a page boundary comes back twice. Creation order only ever gets appended to.
#
# This covers repeats, not skips. A raindrop deleted mid-read shifts the later
# pages the other way and one record is never returned at all, which no dedupe
# can recover. The cost is bounded: a smaller input means a duplicate goes
# unnoticed, never that something is deleted.
SORT = "created"

# The documented limit is 120 requests a minute. Half a second between writes
# keeps a long run comfortably under it without needing to read the headers.
PAUSE_SECONDS = 0.5

# Bounds the pagination loop against a misbehaving API rather than a real
# account: 500 pages is 25,000 raindrops, far beyond anything realistic.
MAX_PAGES = 500


def http_request(method: str, url: str, token: str, payload: dict | None = None) -> dict:
    """Default transport. Injected in tests so nothing here hits the network.

    Retries once on a 429. Requests are paced to stay under the documented
    limit, so this should not fire — but a shared limit is not ours alone to
    reason about, and losing a run halfway to a rate limit would be a poor way
    to find out.
    """
    for attempt in (1, 2):
        try:
            response = requests.request(
                method,
                url,
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
                timeout=30,
            )
        except requests.RequestException as exc:
            # DNS, connection reset, timeout. The commands only catch
            # RaindropError, so a raw requests error would be a traceback.
            raise RaindropError(f"could not reach Raindrop for {method} {url}: {exc}") from exc
        if response.status_code == 429 and attempt == 1:
            time.sleep(_retry_after(response))
            continue
        if response.status_code == 401:
            raise RaindropError(
                "Raindrop rejected the token. Regenerate it at "
                "https://app.raindrop.io/settings/integrations"
            )
        if response.status_code == 429:
            raise RaindropError("Raindrop is rate limiting us; try again in a minute")
        if response.status_code >= 400:
            raise RaindropError(f"Raindrop returned {response.status_code} for {method} {url}")
        try:
            return response.json()
        except ValueError as exc:
            raise RaindropError(f"Raindrop sent a body {method} {url} could not decode") from exc
    raise RaindropError("unreachable")


def _retry_after(response: requests.Response) -> float:
    """How long the API says to wait. `X-RateLimit-Reset` is a UTC epoch
    second, not a duration, so it has to be turned into one."""
    reset = response.headers.get("X-RateLimit-Reset")
    if reset and reset.isdigit():
        return max(1.0, min(60.0, int(reset) - time.time()))
    return 5.0


def to_raindrop(item: dict) -> Raindrop:
    return Raindrop(
        id=item["_id"],
        link=item["link"],
        title=item.get("title", ""),
        tags=tuple(item.get("tags", [])),
        collection_id=item["collection"]["$id"],
        created=item["created"],
    )


class RaindropClient:
    """Reads every bookmark, and writes only what it is told to."""

    def __init__(
        self,
        token: str,
        request: Callable[..., dict] = http_request,
        pause: float = PAUSE_SECONDS,
    ) -> None:
        self._token = token
        self._request = request
        self._pause = pause

    def _call(self, method: str, path: str, payload: dict | None = None) -> dict:
        body = self._request(method, f"{API}{path}", self._token, payload)
        # Every documented response carries `result`. A body without one is not
        # a response this code knows how to read, so it is a failure.
        if not body.get("result"):
            raise RaindropError(body.get("errorMessage", f"{method} {path} was refused"))
        return body

    def all_raindrops(self) -> list[Raindrop]:
        """Every bookmark in the account, one page at a time until a page
        comes back empty.

        Paced like the writes, but only between pages: a single-page account
        pays no pause, and the pause never follows the final page.

        Ids are deduped as pages arrive, keeping the first copy seen.
        `sort=created` should stop a page boundary from repeating a raindrop,
        but a repeat that got through would look like a duplicate of itself and
        be deleted, so it is checked here too rather than trusted to the API.
        """
        found: list[Raindrop] = []
        seen: set[int] = set()
        page = 0
        while True:
            if page >= MAX_PAGES:
                raise RaindropError(f"stopped after {MAX_PAGES} pages of raindrops")
            if page:
                time.sleep(self._pause)
            query = urlencode({"perpage": PAGE_SIZE, "page": page, "sort": SORT})
            body = self._call("GET", f"/raindrops/{ALL_COLLECTIONS}?{query}")
            items = body.get("items", [])
            if not items:
                return found
            for item in items:
                raindrop = to_raindrop(item)
                if raindrop.id in seen:
                    continue
                seen.add(raindrop.id)
                found.append(raindrop)
            page += 1

    def set_tags(self, raindrop_id: int, tags: Sequence[str]) -> None:
        """Replace one raindrop's tags. Batch update appends rather than
        replaces, and each survivor needs a different set, so this is one call
        per survivor — of which there is rarely more than a handful."""
        self._call("PUT", f"/raindrop/{raindrop_id}", {"tags": list(tags)})
        time.sleep(self._pause)

    def move(self, ids: Sequence[int], collection_id: int) -> None:
        """File raindrops into a collection."""
        # An empty batch against collection 0 is an "update everything"
        # request. `_chunks([])` avoids it by arithmetic, not by rule.
        if not ids:
            return
        for chunk in self._chunks(ids):
            self._call(
                "PUT",
                f"/raindrops/{ALL_COLLECTIONS}",
                {"ids": chunk, "collection": {"$id": collection_id}},
            )
            time.sleep(self._pause)

    def delete(self, ids: Sequence[int]) -> None:
        """Move raindrops to Trash, from where they can be restored."""
        # An empty batch against collection 0 is a "delete everything"
        # request. `_chunks([])` avoids it by arithmetic, not by rule.
        if not ids:
            return
        for chunk in self._chunks(ids):
            self._call("DELETE", f"/raindrops/{ALL_COLLECTIONS}", {"ids": chunk})
            time.sleep(self._pause)

    @staticmethod
    def _chunks(ids: Sequence[int]) -> list[list[int]]:
        return [list(ids[i : i + BATCH_SIZE]) for i in range(0, len(ids), BATCH_SIZE)]
