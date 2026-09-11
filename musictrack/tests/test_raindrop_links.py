"""Turning a raindrop into the two links a human might click through on."""

from musictrack.raindrop_links import entry_link, raindrop_url, shop_link

ALBUM = "https://homenormal.bandcamp.com/album/pola"


def test_the_raindrop_url_points_at_the_entry_not_the_shop(make_raindrop):
    """The tool already knows the shop link (`.link`) — this is the other
    URL, the one that opens the bookmark itself in the Raindrop app."""
    raindrop = make_raindrop(link=ALBUM, collection_id=29207263)
    assert raindrop_url(raindrop) == f"https://app.raindrop.io/my/29207263/item/{raindrop.id}/edit"


def test_the_shop_link_is_hyperlinked_to_itself(make_raindrop):
    raindrop = make_raindrop(link=ALBUM)
    assert shop_link(raindrop) == f"[link={ALBUM}]{ALBUM}[/link]"


def test_the_entry_link_points_at_the_raindrop_not_the_shop(make_raindrop):
    """A short label, not the raw URL, so the column stays narrow — the href
    is what matters, not the displayed text."""
    raindrop = make_raindrop(link=ALBUM)
    assert entry_link(raindrop) == f"[link={raindrop_url(raindrop)}]open ↗[/link]"
