"""Talking to Raindrop. The transport is injected, so nothing here reaches the
internet."""

import pytest
import requests

import musictrack.raindrop as raindrop_module
from musictrack.config import load_token
from musictrack.errors import MissingToken, RaindropError
from musictrack.raindrop import RaindropClient, http_request


class FakeTransport:
    """Records every call and answers from a queue of canned responses."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, method, url, token, payload=None):
        self.calls.append((method, url, payload))
        if not self.responses:
            raise AssertionError(f"unexpected extra request: {method} {url}")
        return self.responses.pop(0)


def client(transport):
    """No pause: the rate limiter is not what these tests are about."""
    return RaindropClient("tok", request=transport, pause=0)


def page(items):
    return {"result": True, "items": items}


def raw(id, link="https://example.com/a", tags=("music",), collection=29207263):
    return {
        "_id": id,
        "link": link,
        "title": "An Album",
        "tags": list(tags),
        "collection": {"$id": collection},
        "created": "2026-01-01T00:00:00.000Z",
    }


@pytest.fixture
def responses(monkeypatch):
    """Feed canned HTTP responses to `http_request` without a socket."""

    class Response:
        def __init__(self, status_code, headers=None, json_error=False):
            self.status_code = status_code
            self.headers = headers or {}
            self._json_error = json_error

        def json(self):
            if self._json_error:
                raise ValueError("not JSON")
            return {"result": True}

    queued = []

    def fake_request(method, url, headers=None, json=None, timeout=None):
        queued_next = queued.pop(0)
        # A queued exception stands for the transport failing outright. Raising
        # it here keeps the monkeypatch total: no call reaches a socket.
        if isinstance(queued_next, Exception):
            raise queued_next
        return queued_next

    monkeypatch.setattr(raindrop_module.requests, "request", fake_request)
    monkeypatch.setattr(raindrop_module.time, "sleep", lambda _: None)
    return queued, Response


def test_a_missing_token_file_is_a_clear_error(tmp_path):
    with pytest.raises(MissingToken):
        load_token(tmp_path / "nope")


def test_a_token_is_read_and_stripped(tmp_path):
    path = tmp_path / "token"
    path.write_text("  abc123\n")
    assert load_token(path) == "abc123"


def test_an_empty_token_file_is_a_missing_token(tmp_path):
    path = tmp_path / "token"
    path.write_text("\n")
    with pytest.raises(MissingToken):
        load_token(path)


def test_all_raindrops_pages_until_empty():
    transport = FakeTransport([page([raw(1), raw(2)]), page([raw(3)]), page([])])
    drops = client(transport).all_raindrops()
    assert [d.id for d in drops] == [1, 2, 3]
    assert len(transport.calls) == 3


def test_an_overlapping_page_boundary_yields_each_raindrop_once():
    """A raindrop saved mid-read shifts the pages under us, so the same record
    can end one page and start the next. Two copies of one id normalise to one
    URL, which `build_plan` would read as a duplicate: one copy deleted, the
    other kept. That is a bookmark lost."""
    transport = FakeTransport([page([raw(1), raw(2)]), page([raw(2), raw(3)]), page([])])
    drops = client(transport).all_raindrops()
    assert [d.id for d in drops] == [1, 2, 3]


def test_raindrops_are_read_oldest_first_so_pages_do_not_shift():
    """The default order is creation-descending, where a new raindrop pushes
    every later page along by one. Creation order is only appended to."""
    transport = FakeTransport([page([])])
    client(transport).all_raindrops()
    _, url, _ = transport.calls[0]
    assert "sort=created" in url


def test_all_raindrops_paces_between_pages_but_not_after_the_last(monkeypatch):
    sleeps = []
    monkeypatch.setattr(raindrop_module.time, "sleep", lambda seconds: sleeps.append(seconds))
    transport = FakeTransport([page([raw(1)]), page([raw(2)]), page([])])
    RaindropClient("tok", request=transport, pause=0.5).all_raindrops()
    assert sleeps == [0.5, 0.5]


def test_a_single_page_account_pays_no_pagination_pause(monkeypatch):
    sleeps = []
    monkeypatch.setattr(raindrop_module.time, "sleep", lambda seconds: sleeps.append(seconds))
    transport = FakeTransport([page([])])
    RaindropClient("tok", request=transport, pause=0.5).all_raindrops()
    assert sleeps == []


def test_pagination_is_capped_against_a_misbehaving_api(monkeypatch):
    monkeypatch.setattr(raindrop_module, "MAX_PAGES", 2)
    transport = FakeTransport([page([raw(1)]), page([raw(2)]), page([raw(3)])])
    with pytest.raises(RaindropError, match="pages"):
        client(transport).all_raindrops()


def test_raindrops_are_read_from_every_collection():
    """Collection 0 is 'all'. Reading only the music collection would miss the
    music links sitting in Unsorted."""
    transport = FakeTransport([page([])])
    client(transport).all_raindrops()
    method, url, _ = transport.calls[0]
    assert method == "GET"
    assert "/raindrops/0" in url
    assert "perpage=50" in url


def test_a_raindrop_is_parsed_into_the_model():
    transport = FakeTransport(
        [page([raw(7, link="https://x.com/a", tags=("music", "to-read"))]), page([])]
    )
    [drop] = client(transport).all_raindrops()
    assert drop.id == 7
    assert drop.link == "https://x.com/a"
    assert drop.tags == ("music", "to-read")
    assert drop.collection_id == 29207263
    assert drop.created == "2026-01-01T00:00:00.000Z"


def test_set_tags_writes_one_raindrop():
    transport = FakeTransport([{"result": True}])
    client(transport).set_tags(7, ["music", "to-read"])
    method, url, payload = transport.calls[0]
    assert method == "PUT"
    assert url.endswith("/raindrop/7")
    assert payload == {"tags": ["music", "to-read"]}


def test_move_sends_one_batch():
    transport = FakeTransport([{"result": True}])
    client(transport).move([1, 2, 3], 29207263)
    method, url, payload = transport.calls[0]
    assert method == "PUT"
    assert url.endswith("/raindrops/0")
    assert payload == {"ids": [1, 2, 3], "collection": {"$id": 29207263}}


def test_delete_sends_one_batch_to_the_trash():
    """Collection 0 moves to Trash. Collection -99 would delete permanently,
    and this tool must never send that."""
    transport = FakeTransport([{"result": True}])
    client(transport).delete([1, 2])
    method, url, payload = transport.calls[0]
    assert method == "DELETE"
    assert url.endswith("/raindrops/0")
    assert "-99" not in url
    assert payload == {"ids": [1, 2]}


def test_large_batches_are_chunked():
    ids = list(range(250))
    transport = FakeTransport([{"result": True}] * 3)
    client(transport).delete(ids)
    sent = [payload["ids"] for _, _, payload in transport.calls]
    assert [len(chunk) for chunk in sent] == [100, 100, 50]
    assert [i for chunk in sent for i in chunk] == ids


def test_nothing_to_do_sends_no_request():
    """An empty batch against collection 0 would read as "everything", so both
    writes refuse one outright rather than relying on the chunking."""
    transport = FakeTransport([])
    client(transport).delete([])
    client(transport).move([], 29207263)
    assert transport.calls == []


def test_a_refused_request_raises():
    transport = FakeTransport([{"result": False, "errorMessage": "Unauthorized"}])
    with pytest.raises(RaindropError, match="Unauthorized"):
        client(transport).delete([1])


def test_a_body_without_a_result_key_is_not_treated_as_success():
    """Every documented response carries `result`. A body without one came from
    somewhere this code does not understand, and must not pass for a write that
    worked."""
    transport = FakeTransport([{"items": []}])
    with pytest.raises(RaindropError):
        client(transport).delete([1])


def test_an_unreachable_api_is_a_raindroperror_not_a_requests_traceback(responses):
    """DNS failure, connection reset, timeout. The command only catches
    `RaindropError`."""
    queued, _ = responses
    queued.append(requests.ConnectionError("nodename nor servname provided"))
    with pytest.raises(RaindropError, match="could not reach Raindrop"):
        http_request("GET", "https://x", "tok", None)


def test_a_transport_failure_does_not_report_the_token(responses):
    queued, _ = responses
    queued.append(requests.ConnectionError("boom"))
    with pytest.raises(RaindropError) as caught:
        http_request("GET", "https://x", "sekrit-token", None)
    assert "sekrit-token" not in str(caught.value)


def test_a_dead_token_says_where_to_get_a_new_one(responses):
    queued, Response = responses
    queued.append(Response(401))
    with pytest.raises(RaindropError, match="settings/integrations"):
        http_request("GET", "https://x", "tok", None)


def test_a_rate_limit_is_retried_once_then_reported(responses):
    """Two 429s in a row is a real limit, not a blip."""
    queued, Response = responses
    queued.append(Response(429, {"X-RateLimit-Reset": "0"}))
    queued.append(Response(429, {"X-RateLimit-Reset": "0"}))
    with pytest.raises(RaindropError, match="rate limiting"):
        http_request("GET", "https://x", "tok", None)
    assert queued == []


def test_a_single_rate_limit_is_survived(responses):
    queued, Response = responses
    queued.append(Response(429, {"X-RateLimit-Reset": "0"}))
    queued.append(Response(200))
    assert http_request("GET", "https://x", "tok", None) == {"result": True}


def test_a_server_error_is_a_raindroperror_not_a_raw_http_error(responses):
    """The command that calls this only catches `RaindropError`; a raw
    `requests.HTTPError` would surface as an unhandled traceback."""
    queued, Response = responses
    queued.append(Response(500))
    with pytest.raises(RaindropError, match="500"):
        http_request("GET", "https://x", "tok", None)


def test_a_non_json_body_is_a_raindroperror(responses):
    queued, Response = responses
    queued.append(Response(200, json_error=True))
    with pytest.raises(RaindropError):
        http_request("GET", "https://x", "tok", None)
