"""Child command arguments survive textual-serve's shell boundary."""

import subprocess

import pytest

from ganban.cli.web import _app_command


@pytest.mark.parametrize(
    "executable_name,repo_name",
    [
        ("launcher with spaces", "board"),
        ("launcher", "board with spaces"),
        ("launcher", "board; touch injected"),
        ("launcher", "board$(touch injected)"),
        ("launcher's name", "board's name"),
    ],
)
def test_web_command_preserves_literal_paths(tmp_path, executable_name, repo_name):
    executable = tmp_path / executable_name
    executable.write_text('#!/bin/sh\nprintf "%s\\n" "$#" "$@"\n')
    executable.chmod(0o755)
    repo_path = tmp_path / repo_name
    repo_path.mkdir()
    result = subprocess.run(
        ["/bin/sh", "-c", _app_command(str(executable), str(repo_path))],
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )
    assert not (tmp_path / "injected").exists()
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["1", str(repo_path)]
