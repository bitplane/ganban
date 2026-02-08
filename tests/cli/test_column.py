"""Tests for 'ganban column' commands."""

import json
from argparse import Namespace
from io import StringIO

from ganban.cli.column import (
    column_add,
    column_archive,
    column_get,
    column_list,
    column_move,
    column_rename,
    column_set,
)
from ganban.model.loader import load_board


def test_column_list(initialized_repo, capsys):
    args = Namespace(repo=str(initialized_repo), json=False)
    assert column_list(args) == 0

    out = capsys.readouterr().out
    assert "Backlog" in out
    assert "Doing" in out
    assert "Done" in out
    assert "2 cards" in out


def test_column_list_json(initialized_repo, capsys):
    args = Namespace(repo=str(initialized_repo), json=True)
    assert column_list(args) == 0

    data = json.loads(capsys.readouterr().out)
    assert len(data) == 3
    assert data[0]["id"] == "1"
    assert data[0]["name"] == "Backlog"
    assert data[0]["cards"] == 2


def test_column_get(initialized_repo, capsys):
    args = Namespace(repo=str(initialized_repo), json=False, id="1")
    assert column_get(args) == 0

    out = capsys.readouterr().out
    assert "# Backlog" in out


def test_column_get_json(initialized_repo, capsys):
    args = Namespace(repo=str(initialized_repo), json=True, id="1")
    assert column_get(args) == 0

    data = json.loads(capsys.readouterr().out)
    assert data["id"] == "1"
    assert data["name"] == "Backlog"


def test_column_get_not_found(initialized_repo):
    import pytest

    args = Namespace(repo=str(initialized_repo), json=False, id="99")
    with pytest.raises(SystemExit, match="1"):
        column_get(args)


def test_column_set(initialized_repo, capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", StringIO("# Todo\n\nThings to do.\n"))
    args = Namespace(repo=str(initialized_repo), json=False, id="1")
    assert column_set(args) == 0

    out = capsys.readouterr().out
    assert "Updated column 1" in out

    board = load_board(str(initialized_repo))
    assert board.columns["1"].sections.keys()[0] == "Todo"


def test_column_add(initialized_repo, capsys):
    args = Namespace(repo=str(initialized_repo), json=False, name="Review", hidden=False)
    assert column_add(args) == 0

    out = capsys.readouterr().out
    assert "Created column" in out
    assert "Review" in out

    board = load_board(str(initialized_repo))
    assert len(board.columns) == 4


def test_column_add_json(initialized_repo, capsys):
    args = Namespace(repo=str(initialized_repo), json=True, name="QA", hidden=False)
    assert column_add(args) == 0

    data = json.loads(capsys.readouterr().out)
    assert data["name"] == "QA"
    assert "commit" in data


def test_column_add_hidden(initialized_repo, capsys):
    args = Namespace(repo=str(initialized_repo), json=False, name="Archive", hidden=True)
    assert column_add(args) == 0

    board = load_board(str(initialized_repo))
    col = board.columns["4"]
    assert col.hidden is True


def test_column_move(initialized_repo, capsys):
    args = Namespace(repo=str(initialized_repo), json=False, id="3", position=1)
    assert column_move(args) == 0

    out = capsys.readouterr().out
    assert "Moved column" in out
    assert "Done" in out

    board = load_board(str(initialized_repo))
    names = [board.columns[k].sections.keys()[0] for k in board.columns.keys()]
    assert names[0] == "Done"


def test_column_move_json(initialized_repo, capsys):
    args = Namespace(repo=str(initialized_repo), json=True, id="1", position=3)
    assert column_move(args) == 0

    data = json.loads(capsys.readouterr().out)
    assert "commit" in data


def test_column_rename(initialized_repo, capsys):
    args = Namespace(repo=str(initialized_repo), json=False, id="1", new_name="To Do")
    assert column_rename(args) == 0

    out = capsys.readouterr().out
    assert "Renamed" in out
    assert "To Do" in out

    board = load_board(str(initialized_repo))
    assert board.columns["1"].sections.keys()[0] == "To Do"


def test_column_rename_json(initialized_repo, capsys):
    args = Namespace(repo=str(initialized_repo), json=True, id="2", new_name="In Progress")
    assert column_rename(args) == 0

    data = json.loads(capsys.readouterr().out)
    assert data["old_name"] == "Doing"
    assert data["new_name"] == "In Progress"
    assert "commit" in data


def test_column_archive(initialized_repo, capsys):
    args = Namespace(repo=str(initialized_repo), json=False, id="3")
    assert column_archive(args) == 0

    out = capsys.readouterr().out
    assert "Archived" in out
    assert "Done" in out

    board = load_board(str(initialized_repo))
    assert len(board.columns) == 2


def test_column_archive_json(initialized_repo, capsys):
    args = Namespace(repo=str(initialized_repo), json=True, id="2")
    assert column_archive(args) == 0

    data = json.loads(capsys.readouterr().out)
    assert data["name"] == "Doing"
    assert "commit" in data
