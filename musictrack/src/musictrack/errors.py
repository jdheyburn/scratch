"""Every way this tool gives up, in one place so nothing has to import a
sibling just to catch an exception."""

from __future__ import annotations


class MissingToken(Exception):
    """No Raindrop token where one was expected."""


class RaindropError(Exception):
    """The Raindrop API refused a request."""


class SourceError(Exception):
    """A source this tool reads would not answer."""


class BandcampError(SourceError):
    """Bandcamp refused a request, or answered as a logged-out visitor."""


class SpotifyError(SourceError):
    """Spotify refused a request, or the playlist is not where it should be."""


class LibraryError(SourceError):
    """The beets library on dee could not be read."""
