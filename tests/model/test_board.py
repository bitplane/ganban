"""Tests for board-level helpers."""

from ganban.model.board import create_default_board
from ganban.model.loader import load_board
from ganban.model.writer import save_board
from ganban.parser import first_title


def test_default_board_round_trips(empty_repo):
    """The default board saves and reloads with all three columns."""
    board = create_default_board(empty_repo)
    save_board(board, message="Initialize ganban board")

    loaded = load_board(str(empty_repo))
    assert [first_title(c.sections) for c in loaded.columns] == ["Backlog", "Doing", "Done"]


def test_default_board_backlog_is_compact(empty_repo):
    """Backlog gets the compact flag regardless of which entry point created it."""
    board = create_default_board(empty_repo)
    assert board.columns["1"].meta.compact is True

    save_board(board, message="Initialize ganban board")
    loaded = load_board(str(empty_repo))
    assert loaded.columns["1"].meta.compact is True
