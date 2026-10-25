from typer.testing import CliRunner

from musictrack import __version__
from musictrack.cli import app


def test_version_flag_prints_the_package_version():
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == f"musictrack {__version__}"
