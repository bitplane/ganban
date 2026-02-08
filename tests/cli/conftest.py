"""Shared fixtures for CLI tests."""

import pytest
from git import Repo

from ganban.model.card import create_card
from ganban.model.column import create_column
from ganban.model.node import ListNode, Node
from ganban.model.writer import save_board


@pytest.fixture
def empty_repo(tmp_path):
    """Create an empty git repo."""
    repo = Repo.init(tmp_path)
    (tmp_path / ".gitkeep").write_text("")
    repo.index.add([".gitkeep"])
    repo.index.commit("Initial commit")
    return tmp_path


@pytest.fixture
def initialized_repo(empty_repo):
    """Create a repo with an initialized ganban board (3 columns, 2 cards)."""
    board = Node(repo_path=str(empty_repo))
    board.sections = ListNode()
    board.sections["Test Board"] = "A test board."
    board.meta = {}
    board.cards = ListNode()
    board.columns = ListNode()
    create_column(board, "Backlog", order="1")
    create_column(board, "Doing", order="2")
    create_column(board, "Done", order="3")
    create_card(board, "First card", "Description one.", column=board.columns["1"])
    create_card(board, "Second card", "Description two.", column=board.columns["1"])
    save_board(board, message="Initialize test board")
    return empty_repo
