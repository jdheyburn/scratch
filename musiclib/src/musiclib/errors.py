"""Every way this pipeline gives up, in one place so nothing has to import a
sibling just to catch an exception."""

from __future__ import annotations


class DiscogsError(Exception):
    """Anything that stops us resolving a release or its artwork."""


class BadCover(Exception):
    """The bytes at cover_url aren't a usable image."""


class NotATrack(Exception):
    """A file in an album directory that isn't a numbered track export."""


class RemoteError(Exception):
    """A command run on the music server failed."""
