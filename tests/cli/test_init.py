"""Tests for 'ganban init' command."""

from argparse import Namespace

from ganban.cli.init import init_board
from ganban.model.loader import load_board


def test_init_creates_board(empty_repo, capsys):
    args = Namespace(repo=str(empty_repo), json=False)
    assert init_board(args) == 0

    out = capsys.readouterr().out
    assert "Initialized" in out
    assert "Backlog" in out

    board = load_board(str(empty_repo))
    assert len(board.columns) == 3


def test_init_creates_board_json(empty_repo, capsys):
    args = Namespace(repo=str(empty_repo), json=True)
    assert init_board(args) == 0

    import json

    data = json.loads(capsys.readouterr().out)
    assert data["created"] is True
    assert "Backlog" in data["columns"]


def test_init_idempotent(initialized_repo, capsys):
    args = Namespace(repo=str(initialized_repo), json=False)
    assert init_board(args) == 0

    out = capsys.readouterr().out
    assert "already initialized" in out


def test_init_no_git_repo(tmp_path, capsys):
    args = Namespace(repo=str(tmp_path), json=False)
    assert init_board(args) == 0

    out = capsys.readouterr().out
    assert "Initialized" in out
    assert "Backlog" in out
