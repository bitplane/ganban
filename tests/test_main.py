"""Tests for ganban.__main__ dispatch logic."""

import subprocess
import sys


def _run(*args, cwd=None):
    return subprocess.run(
        [sys.executable, "-m", "ganban", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def test_unknown_subcommand_errors(tmp_path):
    """Unknown first-arg that isn't a valid path exits non-zero with a hint."""
    result = _run("list", cwd=tmp_path)
    assert result.returncode == 2
    assert "unknown subcommand" in result.stderr
    assert "known subcommands" in result.stderr


def test_unknown_subcommand_lists_nouns(tmp_path):
    """Error message names the supported subcommands."""
    result = _run("nope", cwd=tmp_path)
    assert "init" in result.stderr
    assert "card" in result.stderr


def test_help_succeeds(tmp_path):
    """--help still works and exits zero."""
    result = _run("--help", cwd=tmp_path)
    assert result.returncode == 0
    assert "ganban" in result.stdout.lower()
