"""Every way this tool gives up, in one place so nothing has to import a
sibling just to catch an exception."""

from __future__ import annotations


class MissingToken(Exception):
    """No Raindrop token where one was expected."""


class RaindropError(Exception):
    """The Raindrop API refused a request."""
