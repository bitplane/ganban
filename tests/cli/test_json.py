"""JSON output for YAML metadata supported by all document commands."""

import json
import subprocess
import sys

import pytest


@pytest.mark.parametrize("noun,identifier", [("board", []), ("card", ["1"]), ("column", ["1"])])
def test_json_output_serializes_yaml_dates(initialized_repo, noun, identifier):
    prefix = [sys.executable, "-m", "ganban", noun]
    suffix = [*identifier, "--repo", str(initialized_repo), "--json"]
    text = "---\ndue: 2030-01-01\nhistory:\n- at: 2030-01-02T03:04:05+01:00\n---\n# Document\n"
    written = subprocess.run([*prefix, "set", *suffix], input=text, text=True, capture_output=True)
    assert written.returncode == 0, written.stderr
    result = subprocess.run([*prefix, "get", *suffix], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    meta = json.loads(result.stdout)["meta"]
    assert meta["due"] == "2030-01-01"
    assert meta["history"] == [{"at": "2030-01-02T03:04:05+01:00"}]
