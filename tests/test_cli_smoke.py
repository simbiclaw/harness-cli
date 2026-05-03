"""Smoke test: the CLI installs and `--help` and `version` work.

This is the verification floor's lowest baseline. If this test fails, the
package itself is broken.
"""

from __future__ import annotations

from typer.testing import CliRunner

from argus.cli.main import app

runner = CliRunner()


def test_help_runs():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Usage" in result.output


def test_version_runs():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.output.strip() == "0.0.0"
