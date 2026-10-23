"""Tests for 'ganban card' commands."""

import json
import subprocess
import sys
from argparse import Namespace
from io import StringIO

from ganban.cli.card import card_add, card_archive, card_get, card_list, card_move, card_set
from ganban.model.loader import load_board
from ganban.model.writer import save_board


def test_card_list(initialized_repo, capsys):
    args = Namespace(repo=str(initialized_repo), json=False, column=None)
    assert card_list(args) == 0

    out = capsys.readouterr().out
    assert "Backlog" in out
    assert "First card" in out
    assert "Second card" in out


def test_card_list_filter_column(initialized_repo, capsys):
    args = Namespace(repo=str(initialized_repo), json=False, column="2")
    assert card_list(args) == 0

    out = capsys.readouterr().out
    assert "Doing" in out
    assert "First card" not in out


def test_card_list_json(initialized_repo, capsys):
    args = Namespace(repo=str(initialized_repo), json=True, column=None)
    assert card_list(args) == 0

    data = json.loads(capsys.readouterr().out)
    assert len(data) == 2
    assert data[0]["title"] == "First card"
    assert data[0]["column"]["id"] == "1"


def test_card_get(initialized_repo, capsys):
    args = Namespace(repo=str(initialized_repo), json=False, id="001")
    assert card_get(args) == 0

    out = capsys.readouterr().out
    assert "# First card" in out
    assert "Description one." in out


def test_card_get_json(initialized_repo, capsys):
    args = Namespace(repo=str(initialized_repo), json=True, id="001")
    assert card_get(args) == 0

    data = json.loads(capsys.readouterr().out)
    assert data["id"] == "1"
    assert data["title"] == "First card"
    assert data["column"]["name"] == "Backlog"
    assert "# First card" in data["markdown"]


def test_card_get_not_found(initialized_repo):
    import pytest

    args = Namespace(repo=str(initialized_repo), json=False, id="999")
    with pytest.raises(SystemExit, match="1"):
        card_get(args)


def test_card_set(initialized_repo, capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", StringIO("# Updated Title\n\nNew body.\n"))
    args = Namespace(repo=str(initialized_repo), json=False, id="001")
    assert card_set(args) == 0

    out = capsys.readouterr().out
    assert "Updated card 1" in out

    board = load_board(str(initialized_repo))
    assert board.cards["1"].sections.keys()[0] == "Updated Title"


def test_card_set_round_trip(initialized_repo, capsys, monkeypatch):
    """get then set should be a no-op."""
    # Get
    args = Namespace(repo=str(initialized_repo), json=False, id="001")
    card_get(args)
    markdown = capsys.readouterr().out

    # Set with same content
    monkeypatch.setattr("sys.stdin", StringIO(markdown))
    args = Namespace(repo=str(initialized_repo), json=False, id="001")
    card_set(args)
    capsys.readouterr()

    # Verify unchanged
    board = load_board(str(initialized_repo))
    assert board.cards["1"].sections.keys()[0] == "First card"


def test_card_set_rejects_non_string_labels_and_can_repair_existing_data(initialized_repo):
    command = [sys.executable, "-m", "ganban", "card", "set", "1", "--repo", str(initialized_repo), "--json"]
    original = load_board(str(initialized_repo)).commit
    invalid = "---\nlabels: [bug, 123, yes]\n---\n# Card\n"
    result = subprocess.run(command, input=invalid, text=True, capture_output=True)
    assert result.returncode == 1
    assert "labels" in json.loads(result.stderr)["error"]
    assert load_board(str(initialized_repo)).commit == original

    # Hand-edited data must remain readable and repairable through the CLI.
    board = load_board(str(initialized_repo))
    board.cards["1"].meta = {"labels": ["bug", 123, True, None]}
    save_board(board)
    loaded = load_board(str(initialized_repo))
    assert loaded.cards["1"].meta.labels == ["bug", 123, True, None]
    assert list(loaded.labels.keys()) == ["bug"]
    result = subprocess.run(command, input="---\nlabels: [fixed]\n---\n# Card\n", text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert load_board(str(initialized_repo)).cards["1"].meta.labels == ["fixed"]


def test_card_add(initialized_repo, capsys):
    args = Namespace(
        repo=str(initialized_repo),
        json=False,
        title="New card",
        body="Body.",
        column=None,
    )
    assert card_add(args) == 0

    out = capsys.readouterr().out
    assert "Created card 3" in out
    assert "Backlog" in out

    board = load_board(str(initialized_repo))
    assert board.cards["3"] is not None


def test_card_add_to_column(initialized_repo, capsys):
    args = Namespace(
        repo=str(initialized_repo),
        json=False,
        title="In doing",
        body="",
        column="2",
    )
    assert card_add(args) == 0

    board = load_board(str(initialized_repo))
    assert "3" in board.columns["2"].links


def test_card_add_json(initialized_repo, capsys):
    args = Namespace(
        repo=str(initialized_repo),
        json=True,
        title="JSON card",
        body="",
        column=None,
    )
    assert card_add(args) == 0

    data = json.loads(capsys.readouterr().out)
    assert data["id"] == "3"
    assert "commit" in data


def test_card_move(initialized_repo, capsys):
    args = Namespace(repo=str(initialized_repo), json=False, id="001", column="3", position=None)
    assert card_move(args) == 0

    out = capsys.readouterr().out
    assert "Moved card 1 to Done" in out

    board = load_board(str(initialized_repo))
    assert "1" in board.columns["3"].links
    assert "1" not in board.columns["1"].links


def test_card_move_json(initialized_repo, capsys):
    args = Namespace(repo=str(initialized_repo), json=True, id="001", column="2", position=None)
    assert card_move(args) == 0

    data = json.loads(capsys.readouterr().out)
    assert data["column"]["id"] == "2"
    assert "commit" in data


def test_card_archive(initialized_repo, capsys):
    args = Namespace(repo=str(initialized_repo), json=False, id="001")
    assert card_archive(args) == 0

    out = capsys.readouterr().out
    assert "Archived card 1" in out

    board = load_board(str(initialized_repo))
    assert "1" not in board.columns["1"].links
    # Card data still exists
    assert board.cards["1"] is not None


def test_card_archive_json(initialized_repo, capsys):
    args = Namespace(repo=str(initialized_repo), json=True, id="001")
    assert card_archive(args) == 0

    data = json.loads(capsys.readouterr().out)
    assert data["id"] == "1"
    assert "commit" in data
