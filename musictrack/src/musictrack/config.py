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
