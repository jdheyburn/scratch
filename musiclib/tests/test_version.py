from typer.testing import CliRunner

from musiclib import __version__
from musiclib.cli import app


def test_version_flag_prints_the_package_version():
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == f"musiclib {__version__}"
