"""Tests for 'ganban board' commands."""

import json
from argparse import Namespace
from io import StringIO

from ganban.cli.board import board_get, board_set, board_summary
from ganban.model.loader import load_board


def test_board_summary(initialized_repo, capsys):
    args = Namespace(repo=str(initialized_repo), json=False)
    assert board_summary(args) == 0

    out = capsys.readouterr().out
    assert "Test Board" in out
    assert "Backlog" in out
    assert "2 cards" in out


def test_board_summary_json(initialized_repo, capsys):
    args = Namespace(repo=str(initialized_repo), json=True)
    assert board_summary(args) == 0

    data = json.loads(capsys.readouterr().out)
    assert data["title"] == "Test Board"
    assert len(data["columns"]) == 3
    assert data["columns"][0]["name"] == "Backlog"
    assert data["columns"][0]["cards"] == 2


def test_board_get(initialized_repo, capsys):
    args = Namespace(repo=str(initialized_repo), json=False)
    assert board_get(args) == 0

    out = capsys.readouterr().out
    assert "# Test Board" in out
    assert "A test board." in out


def test_board_get_json(initialized_repo, capsys):
    args = Namespace(repo=str(initialized_repo), json=True)
    assert board_get(args) == 0

    data = json.loads(capsys.readouterr().out)
    assert data["title"] == "Test Board"
    assert "# Test Board" in data["markdown"]


def test_board_set(initialized_repo, capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", StringIO("# New Title\n\nNew description.\n"))
    args = Namespace(repo=str(initialized_repo), json=False)
    assert board_set(args) == 0

    out = capsys.readouterr().out
    assert "Updated board" in out

    board = load_board(str(initialized_repo))
    assert board.sections.keys()[0] == "New Title"


def test_board_set_json(initialized_repo, capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", StringIO("# JSON Title\n\nBody.\n"))
    args = Namespace(repo=str(initialized_repo), json=True)
    assert board_set(args) == 0

    data = json.loads(capsys.readouterr().out)
    assert "commit" in data
