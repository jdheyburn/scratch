"""Turning a raindrop into links a human can click through on."""

from __future__ import annotations

from musictrack.models import Raindrop


def raindrop_url(raindrop: Raindrop) -> str:
    """The Raindrop app's own page for this bookmark, not the shop page it
    points to — so a human reviewing a group can open the actual entry."""
    return f"https://app.raindrop.io/my/{raindrop.collection_id}/item/{raindrop.id}/edit"


def shop_link(raindrop: Raindrop) -> str:
    """The shop link, hyperlinked to itself — click through to the release
    page it points to."""
    return f"[link={raindrop.link}]{raindrop.link}[/link]"


def entry_link(raindrop: Raindrop) -> str:
    """A short link to the raindrop's own entry in the Raindrop app, kept
    apart from the shop link so each URL is hyperlinked to itself rather
    than one hiding behind the other's text."""
    return f"[link={raindrop_url(raindrop)}]open ↗[/link]"
