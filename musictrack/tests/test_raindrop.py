"""Turning Raindrop bookmarks into reconcile candidates.

Named `to_listen`, not `wants`, to match `sources/spotify.py`'s adapter for
the same kind of list — a bookmark says "listen to this," not "buy this."
`reconcile`'s own report groups it under its "wants" bucket later, same as
Spotify's; that's the report's vocabulary, not this source's.
"""

from musictrack.sources.raindrop import to_listen


class FakeClient:
    def __init__(self, raindrops):
        self._raindrops = list(raindrops)

    def all_raindrops(self):
        return list(self._raindrops)


def test_a_parseable_bandcamp_bookmark_becomes_a_ref(make_raindrop):
    bookmark = make_raindrop(
        link="https://homenormal.bandcamp.com/album/pola",
        title="Pola | Home Normal",
    )
    [ref] = to_listen(FakeClient([bookmark]))
    assert ref.source == "raindrop"
    assert ref.artist == "Home Normal"
    assert ref.album == "Pola"
    assert ref.ref == str(bookmark.id)
    assert ref.url == bookmark.link


def test_a_non_music_bookmark_is_dropped(make_raindrop):
    bookmark = make_raindrop(tags=(), collection_id=-1)
    assert to_listen(FakeClient([bookmark])) == []


def test_a_bandcamp_daily_bookmark_is_dropped(make_raindrop):
    """parse_release already refuses this whole domain — no separate
    article-exclusion mechanism is needed here."""
    bookmark = make_raindrop(
        link="https://daily.bandcamp.com/best-ambient/the-best-ambient-on-bandcamp-april-2023",
        title="The Best Ambient on Bandcamp: April 2023",
    )
    assert to_listen(FakeClient([bookmark])) == []


def test_a_music_bookmark_on_an_unrecognised_domain_is_dropped(make_raindrop):
    """Default fixture values: a music-tagged link on a domain
    raindrop_identity.py has no parser for."""
    bookmark = make_raindrop()
    assert to_listen(FakeClient([bookmark])) == []


def test_every_bookmark_is_checked_not_just_the_first(make_raindrop):
    daily = make_raindrop(link="https://daily.bandcamp.com/lists/some-list", title="Some List")
    real = make_raindrop(
        link="https://homenormal.bandcamp.com/album/pola",
        title="Pola | Home Normal",
    )
    refs = to_listen(FakeClient([daily, real]))
    assert [r.album for r in refs] == ["Pola"]
