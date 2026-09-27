"""What Plex holds, as two dumps, so a library match can link to its album.

Read from Plex's own SQLite database on dee, opened read-only, rather than
through its HTTP API: the API needs a token, and this needs nothing beyond the
SSH access the beets dumps already use. The database is Plex's internal store,
not a published interface, so a read that breaks costs a run its links and
nothing else.

Only the Music section is read. The Mixes section has the same type, and
reading it would let a library match link to a mix.
"""

from __future__ import annotations

from collections.abc import Callable

from musiclib.remote import run_remote

from musictrack.errors import PlexError
from musictrack.models import AlbumRef

Runner = Callable[[str], str]

DELIMITER = "@@"
MACHINE = "machine"
MUSIC_ROOT = "/mnt/nfs/media/music"
DATABASE = (
    "/var/lib/plex/Plex Media Server/Plug-in Support/Databases/com.plexapp.plugins.library.db"
)
LINK = "https://app.plex.tv/desktop/#!/server/{machine}/details?key=%2Flibrary%2Fmetadata%2F{album}"

ALBUM_QUERY = """
select ar.title, al.title, al.id
from metadata_items al
join metadata_items ar on ar.id = al.parent_id
join library_sections s on s.id = al.library_section_id
join section_locations l on l.library_section_id = s.id
where al.metadata_type = 9 and s.section_type = 8 and l.root_path = ?
"""

# `original_title` holds a track's own artist when it differs from the album
# artist, which is how a featured artist's track is credited.
TRACK_QUERY = """
select coalesce(nullif(t.original_title, ''), ar.title), t.title, al.id
from metadata_items t
join metadata_items al on al.id = t.parent_id
join metadata_items ar on ar.id = al.parent_id
join library_sections s on s.id = t.library_section_id
join section_locations l on l.library_section_id = s.id
where t.metadata_type = 10 and s.section_type = 8 and l.root_path = ?
"""


def link(machine: str, album_id: str) -> str:
    """The album's page in the Plex web app."""
    return LINK.format(machine=machine, album=album_id)


def _script(query: str) -> str:
    """A `python3` program for dee: there is no sqlite3 binary there. The
    first line it prints names the server; `/identity` needs no token."""
    program = "\n".join(
        [
            "import sqlite3, urllib.request, xml.etree.ElementTree as tree",
            "identity = urllib.request.urlopen('http://localhost:32400/identity', timeout=10)",
            "machine = tree.fromstring(identity.read()).get('machineIdentifier')",
            f"print({MACHINE!r} + {DELIMITER!r} + machine)",
            f"db = sqlite3.connect('file:' + {DATABASE!r} + '?mode=ro', uri=True)",
            f"for row in db.execute({query!r}, ({MUSIC_ROOT!r},)):",
            f"    print({DELIMITER!r}.join(str(part) for part in row))",
        ]
    )
    return f"python3 - <<'PY'\n{program}\nPY\n"


def _read(run: Runner, query: str, source: str) -> list[AlbumRef]:
    try:
        output = run(_script(query))
    except Exception as problem:
        raise PlexError(f"could not read Plex: {problem}") from problem
    machine = ""
    rows: list[list[str]] = []
    for line in output.splitlines():
        parts = line.split(DELIMITER)
        if len(parts) == 2 and parts[0] == MACHINE:
            machine = parts[1]
        elif len(parts) == 3:
            rows.append(parts)
    if not machine:
        raise PlexError("Plex did not say which server it is")
    return [
        AlbumRef(
            source=source,
            artist=artist,
            album=title,
            ref=album_id,
            url=link(machine, album_id),
        )
        for artist, title, album_id in rows
    ]


def album_refs(run: Runner = run_remote) -> list[AlbumRef]:
    """Every album in the Music section, each linking to itself."""
    return _read(run, ALBUM_QUERY, "plex-album")


def track_refs(run: Runner = run_remote) -> list[AlbumRef]:
    """Every track in the Music section, carried like a beets track: `album`
    holds the track title. `ref` and `url` are the album the track is on."""
    return _read(run, TRACK_QUERY, "plex-track")
