"""What we write into the FLACs, and why it's more than you'd expect."""

from __future__ import annotations

from pathlib import Path

import mutagen.flac

from musiclib.discogs import Release
from musiclib.errors import NotATrack


def track_number_from_filename(name: str) -> int:
    """Track number from an Audacity export filename (`10.flac` -> 10)."""
    stem = Path(name).stem
    try:
        return int(stem)
    except ValueError:
        raise NotATrack(f"{name}: filename is not a track number") from None


def tags_for(
    filename: str, discogs_id: int | None, release: Release | None = None
) -> dict[str, str]:
    """The fields we write. Deliberately no track titles: those go wrong the
    moment your split disagrees with the tracklist. Album and artist come from
    the release you confirmed by id, so they can't drift — and without them
    beets scores the match against blank tags and reports ~17% for a release
    it found by id.
    """
    tags = {"TRACKNUMBER": str(track_number_from_filename(filename))}
    if discogs_id is not None:
        tags["MUSICBRAINZ_ALBUMID"] = str(discogs_id)
    if release is not None:
        tags["ALBUM"] = release.album
        tags["ALBUMARTIST"] = release.artist
        # Repressings share artist, album and track count, so without these a
        # reissue outranks the release you asked for — measured 7th of 10 for
        # Substance & Vainqueur. The year alone moves it to 1st.
        if release.year:
            tags["DATE"] = str(release.year)
        if release.catalogue:
            tags["CATALOGNUMBER"] = release.catalogue
        if release.format:
            tags["MEDIA"] = release.format
        if release.label:
            tags["LABEL"] = release.label
    return tags


def album_flacs(directory: Path) -> list[Path]:
    """Numbered track exports, in track order. Anything else is ignored."""
    tracks = []
    for f in directory.glob("*.flac"):
        try:
            tracks.append((track_number_from_filename(f.name), f))
        except NotATrack:
            continue
    return [f for _, f in sorted(tracks)]


def tag_album(directory: Path, discogs_id: int | None, release: Release | None = None) -> int:
    """Write the two fields beets needs. Returns how many tracks were tagged.

    Done before transfer, so rsync sees final bytes and stays incremental.
    """
    tracks = album_flacs(directory)
    for path in tracks:
        audio = mutagen.flac.FLAC(path)
        for key, value in tags_for(path.name, discogs_id, release).items():
            audio[key] = value
        audio.save()
    return len(tracks)
