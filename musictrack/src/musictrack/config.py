"""Where the credentials live.

A Raindrop personal test token, from the app management console. The tool only
ever reads one account — its own — so there is no OAuth flow to run.
"""

from __future__ import annotations

from pathlib import Path

from musictrack.errors import MissingToken

TOKEN_PATH = Path.home() / ".config" / "raindrop" / "token"

HOW_TO_GET_ONE = (
    f"No Raindrop token at {TOKEN_PATH}.\n"
    "Create an app at https://app.raindrop.io/settings/integrations, then:\n"
    "  mkdir -p ~/.config/raindrop && read -s t && "
    'printf %s "$t" > ~/.config/raindrop/token && chmod 600 ~/.config/raindrop/token'
)


def load_token(path: Path | None = None) -> str:
    """The token, or a message saying how to make one."""
    path = path or TOKEN_PATH
    if not path.is_file():
        raise MissingToken(HOW_TO_GET_ONE)
    token = path.read_text().strip()
    if not token:
        raise MissingToken(HOW_TO_GET_ONE)
    return token


BANDCAMP_COOKIE_PATH = Path.home() / ".config" / "bandcamp" / "cookie"
SPOTIFY_DIR = Path.home() / ".config" / "spotify"

HOW_TO_GET_A_COOKIE = (
    f"No Bandcamp cookies at {BANDCAMP_COOKIE_PATH}.\n"
    "Log in at bandcamp.com in Firefox, then copy the whole jar:\n"
    "  cp ~/Library/Application\\ Support/Firefox/Profiles/*/cookies.sqlite /tmp/ffc.sqlite\n"
    "  sqlite3 /tmp/ffc.sqlite \"select group_concat(name || '=' || value, '; ') "
    "from moz_cookies where host='.bandcamp.com';\" | tr -d '\\n' > ~/.config/bandcamp/cookie\n"
    "  chmod 600 ~/.config/bandcamp/cookie && rm -f /tmp/ffc.sqlite\n"
    "The whole jar, not just `identity`: on its own it reads as a logged-out visitor."
)

HOW_TO_GET_SPOTIFY_CREDENTIALS = (
    "Create an app at https://developer.spotify.com/dashboard with redirect URI\n"
    "http://127.0.0.1:8888/callback (Spotify rejects `localhost`), then write\n"
    f"its Client ID to {SPOTIFY_DIR / 'client_id'} and its Client Secret to\n"
    f"{SPOTIFY_DIR / 'client_secret'}, both mode 600."
)


def load_bandcamp_cookie(path: Path | None = None) -> str:
    """The whole cookie jar for .bandcamp.com, as one Cookie header."""
    path = path or BANDCAMP_COOKIE_PATH
    if not path.is_file():
        raise MissingToken(HOW_TO_GET_A_COOKIE)
    cookie = path.read_text().strip()
    if not cookie:
        raise MissingToken(HOW_TO_GET_A_COOKIE)
    return cookie


def load_spotify_credentials(directory: Path | None = None) -> tuple[str, str]:
    """Client id and secret. Both, or neither is any use."""
    directory = directory or SPOTIFY_DIR
    values = []
    for name in ("client_id", "client_secret"):
        path = directory / name
        if not path.is_file() or not path.read_text().strip():
            raise MissingToken(f"No Spotify {name} at {path}.\n{HOW_TO_GET_SPOTIFY_CREDENTIALS}")
        values.append(path.read_text().strip())
    return values[0], values[1]
