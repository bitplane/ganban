"""Tests for the Node-tree board loader."""

import shutil
import tempfile
from pathlib import Path

import pytest
from git import Repo

from ganban.model.loader import load_board
from ganban.model.node import ListNode, Node


@pytest.fixture
def sample_board(tmp_path):
    """Create a sample board as a git repo with ganban branch."""
    repo = Repo.init(tmp_path)

    # Create initial commit on main so we can create branches
    (tmp_path / ".gitkeep").write_text("")
    repo.index.add([".gitkeep"])
    repo.index.commit("Initial commit")

    # Create board structure in a temp dir OUTSIDE the repo
    with tempfile.TemporaryDirectory() as board_tmp:
        board_dir = Path(board_tmp)

        # Create .all/ with cards
        all_dir = board_dir / ".all"
        all_dir.mkdir()
        (all_dir / "001.md").write_text("# Fix login bug\n\nDescription here.\n\n## Notes\n\nSome notes.")
        (all_dir / "002.md").write_text("# Add feature\n\nAnother card.")
        (all_dir / "003.md").write_text("---\ntags:\n - urgent\n---\n# Refactor API\n\nWith meta.")

        # Create columns
        backlog = board_dir / "1.backlog"
        backlog.mkdir()
        (backlog / "01.fix-login-bug.md").symlink_to("../.all/001.md")

        doing = board_dir / "2.in-progress"
        doing.mkdir()
        (doing / "index.md").write_text("---\ncolor: blue\n---\n# Doing\n\nActive work.")
        (doing / "01.add-feature.md").symlink_to("../.all/002.md")
        (doing / "02.refactor-api.md").symlink_to("../.all/003.md")

        done = board_dir / "3.done"
        done.mkdir()
        (done / ".gitkeep").write_text("")

        # Root index
        (board_dir / "index.md").write_text("# My Project Board\n\nBoard description.\n\n## Info\n\nExtra info.")

        # Create orphan branch and commit the board structure
        repo.git.checkout("--orphan", "ganban")
        repo.git.rm("-rf", ".", "--cached")
        repo.git.clean("-fd")

        # Copy board files to repo root
        for item in board_dir.iterdir():
            dest = tmp_path / item.name
            if item.is_dir():
                shutil.copytree(item, dest, symlinks=True)
            else:
                shutil.copy2(item, dest)

    repo.git.add("-A")
    repo.index.commit("Initial board")

    return tmp_path


def test_load_board_returns_node(sample_board):
    board = load_board(str(sample_board))
    assert isinstance(board, Node)


def test_load_board_has_columns(sample_board):
    board = load_board(str(sample_board))
    assert isinstance(board.columns, ListNode)
    assert len(board.columns) == 3


def test_load_board_has_cards(sample_board):
    board = load_board(str(sample_board))
    assert isinstance(board.cards, ListNode)
    assert len(board.cards) == 3
    assert board.cards["001"] is not None
    assert board.cards["002"] is not None
    assert board.cards["003"] is not None


def test_load_board_column_properties(sample_board):
    board = load_board(str(sample_board))
    col = board.columns["1"]
    assert col.sections.keys()[0] == "Backlog"
    assert col.order == "1"
    assert col.dir_path == "1.backlog"
    assert col.hidden is False


def test_load_board_column_links(sample_board):
    board = load_board(str(sample_board))

    backlog = board.columns["1"]
    assert isinstance(backlog.links, list)
    assert backlog.links == ["001"]

    doing = board.columns["2"]
    assert doing.links == ["002", "003"]

    done = board.columns["3"]
    assert done.links == []


def test_load_board_card_sections(sample_board):
    board = load_board(str(sample_board))
    card = board.cards["001"]
    assert isinstance(card.sections, ListNode)
    assert card.sections["Fix login bug"] == "Description here."
    assert card.sections["Notes"] == "Some notes."


def test_load_board_card_meta(sample_board):
    board = load_board(str(sample_board))
    card = board.cards["003"]
    assert isinstance(card.meta, Node)
    assert card.meta.tags == ["urgent"]


def test_load_board_column_meta(sample_board):
    board = load_board(str(sample_board))
    col = board.columns["2"]
    assert isinstance(col.meta, Node)
    assert col.meta.color == "blue"


def test_load_board_root_sections(sample_board):
    board = load_board(str(sample_board))
    assert isinstance(board.sections, ListNode)
    assert board.sections["My Project Board"] == "Board description."
    assert board.sections["Info"] == "Extra info."


def test_load_board_column_name_from_index(sample_board):
    board = load_board(str(sample_board))
    doing = board.columns["2"]
    assert doing.sections.keys()[0] == "Doing"


def test_load_board_commit(sample_board):
    board = load_board(str(sample_board))
    assert len(board.commit) == 40

    repo = Repo(sample_board)
    assert board.commit == repo.commit("ganban").hexsha


def test_load_board_missing_branch(tmp_path):
    repo = Repo.init(tmp_path)
    (tmp_path / ".gitkeep").write_text("")
    repo.index.add([".gitkeep"])
    repo.index.commit("Initial")

    with pytest.raises(ValueError, match="Branch 'ganban' not found"):
        load_board(str(tmp_path))
