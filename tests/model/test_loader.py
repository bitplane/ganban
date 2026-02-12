"""Tests for the Node-tree board loader."""

import shutil
import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from git import Repo
from git.util import Actor

from ganban.model.card import archive_card, move_card
from ganban.model.loader import _activate, _get_committers, _load_tree, file_creation_date, load_board
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
    assert board.cards["1"] is not None
    assert board.cards["2"] is not None
    assert board.cards["3"] is not None


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
    assert isinstance(backlog.links, tuple)
    assert backlog.links == ("1",)

    doing = board.columns["2"]
    assert doing.links == ("2", "3")

    done = board.columns["3"]
    assert done.links == ()


def test_load_board_card_sections(sample_board):
    board = load_board(str(sample_board))
    card = board.cards["1"]
    assert isinstance(card.sections, ListNode)
    assert card.sections["Fix login bug"] == "Description here."
    assert card.sections["Notes"] == "Some notes."


def test_load_board_card_meta(sample_board):
    board = load_board(str(sample_board))
    card = board.cards["3"]
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


def test_load_board_has_git_node(sample_board):
    board = load_board(str(sample_board))
    assert isinstance(board.git, Node)
    assert isinstance(board.git.committers, list)


def test_load_board_git_committers_populated(sample_board):
    """Committers list contains the author from the fixture's commits."""
    board = load_board(str(sample_board))
    assert len(board.git.committers) > 0
    # Each entry should be "Name <email>" format
    for entry in board.git.committers:
        assert "<" in entry and ">" in entry


def test_get_committers_deduplicates(tmp_path):
    """Multiple commits by same author produce one entry."""
    repo = Repo.init(tmp_path)
    (tmp_path / "a.txt").write_text("a")
    repo.index.add(["a.txt"])
    repo.index.commit("first", author=Actor("Alice", "alice@example.com"))
    (tmp_path / "b.txt").write_text("b")
    repo.index.add(["b.txt"])
    repo.index.commit("second", author=Actor("Alice", "alice@example.com"))
    result = _get_committers(repo)
    assert result.count("Alice <alice@example.com>") == 1


def test_get_committers_multiple_authors(tmp_path):
    """Different authors produce separate entries, sorted."""
    repo = Repo.init(tmp_path)
    (tmp_path / "a.txt").write_text("a")
    repo.index.add(["a.txt"])
    repo.index.commit("first", author=Actor("Bob", "bob@example.com"))
    (tmp_path / "b.txt").write_text("b")
    repo.index.add(["b.txt"])
    repo.index.commit("second", author=Actor("Alice", "alice@example.com"))
    result = _get_committers(repo)
    assert result == ["Alice <alice@example.com>", "Bob <bob@example.com>"]


def test_load_board_adopts_regular_file_as_card(tmp_path):
    """A regular .md file in a column directory is adopted as a new card."""
    repo = Repo.init(tmp_path)
    (tmp_path / ".gitkeep").write_text("")
    repo.index.add([".gitkeep"])
    repo.index.commit("Initial commit")

    with tempfile.TemporaryDirectory() as board_tmp:
        board_dir = Path(board_tmp)

        all_dir = board_dir / ".all"
        all_dir.mkdir()
        (all_dir / "001.md").write_text("# Existing card\n\nAlready here.")

        backlog = board_dir / "1.backlog"
        backlog.mkdir()
        (backlog / "01.existing-card.md").symlink_to("../.all/001.md")
        # Regular file, not a symlink
        (backlog / "02.new-card.md").write_text("# Adopted card\n\nFrom a file.")

        (board_dir / "index.md").write_text("# Board\n")

        repo.git.checkout("--orphan", "ganban")
        repo.git.rm("-rf", ".", "--cached")
        repo.git.clean("-fd")

        for item in board_dir.iterdir():
            dest = tmp_path / item.name
            if item.is_dir():
                shutil.copytree(item, dest, symlinks=True)
            else:
                shutil.copy2(item, dest)

    repo.git.add("-A")
    repo.index.commit("Board with regular file")

    board = load_board(str(tmp_path))

    # Should have 2 cards: the original and the adopted one
    assert len(board.cards) == 2

    # The adopted card should be in the backlog links
    backlog = board.columns["1"]
    assert len(backlog.links) == 2
    assert "1" in backlog.links

    # Find the adopted card
    adopted_id = [lid for lid in backlog.links if lid != "1"][0]
    adopted = board.cards[adopted_id]
    assert adopted.sections["Adopted card"] == "From a file."


def test_load_board_adopted_card_survives_save(tmp_path):
    """An adopted regular file becomes a proper symlinked card after save."""
    repo = Repo.init(tmp_path)
    (tmp_path / ".gitkeep").write_text("")
    repo.index.add([".gitkeep"])
    repo.index.commit("Initial commit")

    with tempfile.TemporaryDirectory() as board_tmp:
        board_dir = Path(board_tmp)

        all_dir = board_dir / ".all"
        all_dir.mkdir()

        backlog = board_dir / "1.backlog"
        backlog.mkdir()
        (backlog / "01.dropped-in.md").write_text("# Dropped in\n\nVia vim.")

        (board_dir / "index.md").write_text("# Board\n")

        repo.git.checkout("--orphan", "ganban")
        repo.git.rm("-rf", ".", "--cached")
        repo.git.clean("-fd")

        for item in board_dir.iterdir():
            dest = tmp_path / item.name
            if item.is_dir():
                shutil.copytree(item, dest, symlinks=True)
            else:
                shutil.copy2(item, dest)

    repo.git.add("-A")
    repo.index.commit("Board with dropped file")

    from ganban.model.writer import save_board

    board = load_board(str(tmp_path))
    assert len(board.cards) == 1
    save_board(board, message="Adopt card")

    # Reload and verify it's now a proper card
    reloaded = load_board(str(tmp_path))
    assert len(reloaded.cards) == 1
    card = list(reloaded.cards)[0]
    assert card.sections["Dropped in"] == "Via vim."
    assert reloaded.columns["1"].links[0] == list(reloaded.cards.keys())[0]


def test_file_creation_date_returns_datetime(repo_with_ganban):
    """Returns the author date of the commit that first added a file."""
    result = file_creation_date(str(repo_with_ganban), ".all/001.md")
    assert result is not None
    assert isinstance(result, datetime)


def test_file_creation_date_returns_none_for_missing_file(repo_with_ganban):
    """Returns None for a file that doesn't exist on the branch."""
    result = file_creation_date(str(repo_with_ganban), ".all/999.md")
    assert result is None


def test_file_creation_date_returns_first_commit(repo_with_ganban):
    """If a file is modified later, we still get the original creation date."""
    repo = Repo(repo_with_ganban)
    repo.git.checkout("ganban")

    # Modify the card in a second commit
    card_path = repo_with_ganban / ".all" / "001.md"
    original_date = file_creation_date(str(repo_with_ganban), ".all/001.md")

    card_path.write_text("# First card\n\nEdited description.\n")
    repo.index.add([".all/001.md"])
    repo.index.commit("Edit card")

    result = file_creation_date(str(repo_with_ganban), ".all/001.md")
    assert result == original_date


def test_file_creation_date_different_files(repo_with_ganban):
    """Different files added in different commits get different dates."""
    repo = Repo(repo_with_ganban)
    repo.git.checkout("ganban")

    date_001 = file_creation_date(str(repo_with_ganban), ".all/001.md")

    # Add a second card in a new commit
    (repo_with_ganban / ".all" / "002.md").write_text("# Second card\n")
    repo.index.add([".all/002.md"])
    repo.index.commit("Add second card")

    date_002 = file_creation_date(str(repo_with_ganban), ".all/002.md")
    assert date_001 is not None
    assert date_002 is not None
    assert date_002 >= date_001


def test_load_board_missing_branch(tmp_path):
    repo = Repo.init(tmp_path)
    (tmp_path / ".gitkeep").write_text("")
    repo.index.add([".gitkeep"])
    repo.index.commit("Initial")

    with pytest.raises(ValueError, match="Branch 'ganban' not found"):
        load_board(str(tmp_path))


def test_load_tree_has_no_git_node(sample_board):
    """_load_tree returns a board with no git node."""
    repo = Repo(sample_board)
    tree = repo.commit("ganban").tree
    board = _load_tree(tree)
    assert "git" not in board


def test_load_tree_has_no_repo_path(sample_board):
    """_load_tree returns a board with no repo_path."""
    repo = Repo(sample_board)
    tree = repo.commit("ganban").tree
    board = _load_tree(tree)
    assert "repo_path" not in board


def test_load_tree_has_cards_and_columns(sample_board):
    """_load_tree returns a board with cards and columns populated."""
    repo = Repo(sample_board)
    tree = repo.commit("ganban").tree
    board = _load_tree(tree)
    assert isinstance(board.cards, ListNode)
    assert len(board.cards) == 3
    assert isinstance(board.columns, ListNode)
    assert len(board.columns) == 3


def test_activate_adds_git_node(sample_board):
    """_activate attaches a git node with committers and config."""
    repo = Repo(sample_board)
    tree = repo.commit("ganban").tree
    board = _load_tree(tree)
    board.repo_path = str(sample_board)
    _activate(board, repo)
    assert isinstance(board.git, Node)
    assert isinstance(board.git.committers, list)
    assert isinstance(board.git.config, Node)


def test_links_are_tuples(sample_board):
    """Column links are tuples after loading."""
    board = load_board(str(sample_board))
    for col in board.columns:
        assert isinstance(col.links, tuple)


def test_card_not_archived_when_in_column(sample_board):
    """Cards linked from a column are not archived."""
    board = load_board(str(sample_board))
    assert board.cards["1"].archived is False
    assert board.cards["2"].archived is False
    assert board.cards["3"].archived is False


def test_card_archived_when_not_in_column(sample_board):
    """Cards in .all but not in any column are archived."""
    board = load_board(str(sample_board))
    archive_card(board, "1")
    assert board.cards["1"].archived is True


def test_card_becomes_archived_on_remove(sample_board):
    """Removing a card from its column marks it archived."""
    board = load_board(str(sample_board))
    assert board.cards["1"].archived is False
    archive_card(board, "1")
    assert board.cards["1"].archived is True


def test_card_unarchived_on_add(sample_board):
    """Adding a card to a column marks it not archived."""
    board = load_board(str(sample_board))
    archive_card(board, "1")
    assert board.cards["1"].archived is True
    move_card(board, "1", board.columns["2"])
    assert board.cards["1"].archived is False


def test_card_not_blocked_without_deps(sample_board):
    """A card with no deps is not blocked."""
    board = load_board(str(sample_board))
    assert board.cards["1"].blocked is None


def test_card_blocked_by_unready_dep(sample_board):
    """A card depending on an active (not ready) card is blocked."""
    board = load_board(str(sample_board))
    board.cards["1"].meta.deps = ["2"]
    assert board.cards["1"].blocked is True


def test_card_not_blocked_when_dep_done(sample_board):
    """A card whose dep is marked done is not blocked."""
    board = load_board(str(sample_board))
    board.cards["2"].meta.done = True
    board.cards["1"].meta.deps = ["2"]
    assert board.cards["1"].blocked is None


def test_card_not_blocked_when_dep_archived(sample_board):
    """A card whose dep is archived is not blocked."""
    board = load_board(str(sample_board))
    archive_card(board, "2")
    board.cards["1"].meta.deps = ["2"]
    assert board.cards["1"].blocked is None


def test_card_unblocked_when_dep_completed(sample_board):
    """Marking a dep as done unblocks the dependent card."""
    board = load_board(str(sample_board))
    board.cards["1"].meta.deps = ["2"]
    assert board.cards["1"].blocked is True
    board.cards["2"].meta.done = True
    assert board.cards["1"].blocked is None


def test_card_unblocked_when_dep_archived(sample_board):
    """Archiving a dep unblocks the dependent card."""
    board = load_board(str(sample_board))
    board.cards["1"].meta.deps = ["2"]
    assert board.cards["1"].blocked is True
    archive_card(board, "2")
    assert board.cards["1"].blocked is None


def test_card_blocked_missing_dep_ignored(sample_board):
    """A dep ID that doesn't exist in cards is skipped."""
    board = load_board(str(sample_board))
    board.cards["1"].meta.deps = ["999"]
    assert board.cards["1"].blocked is None
