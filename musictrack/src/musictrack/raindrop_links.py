"""Turning a raindrop into a link a human can click through on."""

from __future__ import annotations

from musictrack.models import Raindrop


def raindrop_url(raindrop: Raindrop) -> str:
    """The Raindrop app's own page for this bookmark, not the shop page it
    points to — so a human reviewing a group can open the actual entry."""
    return f"https://app.raindrop.io/my/{raindrop.collection_id}/item/{raindrop.id}/edit"


def linked(raindrop: Raindrop) -> str:
    """The shop link as displayed text, hyperlinked to the raindrop entry
    behind it. Terminals without hyperlink support just show the text."""
    return f"[link={raindrop_url(raindrop)}]{raindrop.link}[/link]"
