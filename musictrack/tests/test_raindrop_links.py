"""Turning a raindrop's shop link into something that opens the entry itself."""

from musictrack.raindrop_links import linked, raindrop_url

ALBUM = "https://homenormal.bandcamp.com/album/pola"


def test_the_raindrop_url_points_at_the_entry_not_the_shop(make_raindrop):
    """The tool already knows the shop link (`.link`) — this is the other
    URL, the one that opens the bookmark itself in the Raindrop app."""
    raindrop = make_raindrop(link=ALBUM, collection_id=29207263)
    assert raindrop_url(raindrop) == f"https://app.raindrop.io/my/29207263/item/{raindrop.id}/web"


def test_the_linked_cell_shows_the_shop_link_as_the_label(make_raindrop):
    """The visible text stays the shop link a human recognises; only the
    hyperlink target changes to the raindrop entry."""
    raindrop = make_raindrop(link=ALBUM)
    assert linked(raindrop) == f"[link={raindrop_url(raindrop)}]{ALBUM}[/link]"
