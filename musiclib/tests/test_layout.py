"""The shape of the package itself.

`musiclib` was one 1,100-line module. These tests hold the split in place: one
file per command, no import cycles, and no module quietly growing back into a
god-file.
"""

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

import musiclib
from musiclib.cli import app

COMMANDS = ["sync", "done", "gc", "reconcile"]

# Long enough for the busiest command, short enough that a module doing two
# jobs will trip it.
MAX_MODULE_LINES = 200

PACKAGE_DIR = Path(musiclib.__file__).parent


def vinyl_commands():
    [group] = app.registered_groups
    vinyl = group.typer_instance
    assert vinyl is not None
    # Typer derives an unnamed command's name from its function, and types
    # callbacks as plain Callable — which need not carry a __name__.
    return {
        c.name or getattr(c.callback, "__name__", ""): c.callback
        for c in vinyl.registered_commands
        if c.callback is not None
    }


@pytest.mark.parametrize("name", COMMANDS)
def test_every_vinyl_command_is_reachable_from_the_cli(name):
    assert name in vinyl_commands()


@pytest.mark.parametrize("name", COMMANDS)
def test_each_command_lives_in_its_own_module(name):
    assert vinyl_commands()[name].__module__ == f"musiclib.commands.{name}"


def test_the_cli_exposes_nothing_but_those_commands():
    """A command that isn't in COMMANDS is one this file forgot to describe."""
    assert sorted(vinyl_commands()) == sorted(COMMANDS)


def test_no_module_has_grown_back_into_a_god_file():
    oversized = {
        path.relative_to(PACKAGE_DIR).as_posix(): len(path.read_text().splitlines())
        for path in PACKAGE_DIR.rglob("*.py")
        if len(path.read_text().splitlines()) > MAX_MODULE_LINES
    }
    assert not oversized


def test_every_module_can_be_imported_first():
    """Each module imported into a clean interpreter, so a cycle can't hide
    behind whichever module the test suite happened to load first."""
    modules = sorted(
        "musiclib." + p.relative_to(PACKAGE_DIR).with_suffix("").as_posix().replace("/", ".")
        for p in PACKAGE_DIR.rglob("*.py")
        if p.stem != "__init__"
    )
    script = textwrap.dedent(
        """
        import importlib, sys
        for name in sys.argv[1:]:
            for loaded in [m for m in sys.modules if m.startswith("musiclib")]:
                del sys.modules[loaded]
            importlib.import_module(name)
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script, *modules], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
