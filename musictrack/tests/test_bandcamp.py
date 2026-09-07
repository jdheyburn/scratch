"""Talking to Bandcamp. The transport is injected; nothing here reaches the
internet."""

import pytest

from musictrack.errors import BandcampError
from musictrack.sources.bandcamp import BandcampClient, to_ref


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, method, url, cookie, payload=None):
        self.calls.append((method, url, payload))
        if not self.responses:
            raise AssertionError(f"unexpected extra request: {method} {url}")
        return self.responses.pop(0)


def client(transport):
    return BandcampClient("identity=x; js_logged_in=1", request=transport, pause=0)


def summary_body(purchased=2, wishlisted=1):
    lookup = {f"p{i}": {"purchased": True} for i in range(purchased)}
    lookup.update({f"w{i}": {"purchased": False} for i in range(wishlisted)})
    return {"fan_id": 4242, "collection_summary": {"tralbum_lookup": lookup}}


def item(item_id, title="An Album", band="An Artist", item_type="album"):
    return {
        "item_id": item_id,
        "item_type": item_type,
        "band_name": band,
        "item_title": title,
        "item_url": f"https://example.bandcamp.com/album/{item_id}",
        "token": f"{item_id}::a::",
    }


def page(items, more=True, last=None):
    return {
        "items": items,
        "more_available": more,
        "last_token": last or (items[-1]["token"] if items else None),
    }


def test_the_summary_separates_purchases_from_wishes():
    transport = FakeTransport([summary_body(purchased=377, wishlisted=845)])
    found = client(transport).summary()
    assert found.fan_id == 4242
    assert (found.purchased, found.wishlisted) == (377, 845)


def test_a_logged_out_session_is_reported_as_expired_credentials():
    """Bandcamp answers an anonymous request with HTTP 200 and no fan, so a
    stale cookie otherwise looks like an account with nothing in it."""
    transport = FakeTransport([{"collection_summary": {}}])
    with pytest.raises(BandcampError) as problem:
        client(transport).summary()
    assert "log" in str(problem.value).lower() or "expired" in str(problem.value).lower()


def test_the_cookie_never_appears_in_an_error():
    transport = FakeTransport([{"collection_summary": {}}])
    with pytest.raises(BandcampError) as problem:
        client(transport).summary()
    assert "js_logged_in" not in str(problem.value)


def test_a_cycling_cursor_stops_instead_of_looping():
    """The real collection endpoint returns to an earlier token after about
    four pages and keeps saying more_available, serving the same items for
    ever. Followed naively this read 1497 rows holding 377 items."""
    first = page([item(1), item(2)])
    repeat = page([item(1), item(2)])
    transport = FakeTransport([summary_body(purchased=2, wishlisted=0), first, repeat])
    found = client(transport).collection()
    assert [r.ref for r in found] == ["1", "2"]


def test_a_short_read_is_an_error_rather_than_a_quiet_wrong_answer():
    """The summary says how many purchases exist. Reading fewer means records
    were lost, and a lost record reads as `not in the library`."""
    transport = FakeTransport(
        [summary_body(purchased=9, wishlisted=0), page([item(1)], more=False)]
    )
    with pytest.raises(BandcampError) as problem:
        client(transport).collection()
    assert "9" in str(problem.value)


def test_items_become_refs_carrying_the_source_id():
    transport = FakeTransport(
        [
            summary_body(purchased=1, wishlisted=0),
            page([item(7, "Interstate", "Monolake")], more=False),
        ]
    )
    [ref] = client(transport).collection()
    assert (ref.source, ref.artist, ref.album, ref.ref) == (
        "bandcamp-collection",
        "Monolake",
        "Interstate",
        "7",
    )


def test_the_wishlist_is_read_from_its_own_endpoint():
    transport = FakeTransport(
        [summary_body(purchased=0, wishlisted=1), page([item(3)], more=False)]
    )
    client(transport).wishlist()
    _, url, _ = transport.calls[1]
    assert url.endswith("/wishlist_items")


def test_a_missing_item_id_becomes_an_empty_ref_not_the_string_none():
    """A dismissal keyed off the literal text 'None' would hide every item
    missing an id under one dismissal."""
    ref = to_ref({"band_name": "An Artist", "item_title": "An Album"}, "bandcamp-collection")
    assert ref.ref == ""


def test_a_single_default_run_reads_the_summary_once():
    """collection() and wishlist() both need the summary. A default reconcile
    run calls both, and that must not mean two identical GETs."""
    transport = FakeTransport(
        [
            summary_body(purchased=1, wishlisted=1),
            page([item(1)], more=False),
            page([item(2)], more=False),
        ]
    )
    account = client(transport)
    account.collection()
    account.wishlist()
    summary_calls = [call for call in transport.calls if call[1].endswith("collection_summary")]
    assert len(summary_calls) == 1


def test_an_unusable_summary_is_an_error_not_a_silent_zero():
    """A summary with no tralbum_lookup at all would make `expected` 0, and a
    lost paged read of 0 never trips the shortfall guard."""
    transport = FakeTransport([{"fan_id": 4242, "collection_summary": {}}])
    with pytest.raises(BandcampError):
        client(transport).summary()
