"""Tests for board loader."""

from pathlib import Path

import pytest
from git import Repo

from ganban.loader import (
    _parse_dirname,
    _parse_link_name,
    load_board,
)


@pytest.fixture
def sample_board(tmp_path):
    """Create a sample board as a git repo with ganban branch."""
    import shutil
    import tempfile

    # Initialize repo
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
        (all_dir / "001.md").write_text("# Fix login bug\n\nDescription here.")
        (all_dir / "002.md").write_text("# Add feature\n\nAnother card.")
        (all_dir / "003.md").write_text("---\ntags:\n - urgent\n---\n# Refactor API\n\nWith meta.")

        # Create columns
        backlog = board_dir / "1.backlog"
        backlog.mkdir()
        (backlog / "01.fix-login-bug.md").symlink_to("../.all/001.md")

        doing = board_dir / "2.in-progress"
        doing.mkdir()
        (doing / "01.add-feature.md").symlink_to("../.all/002.md")
        (doing / "02.refactor-api.md").symlink_to("../.all/003.md")

        done = board_dir / "3.done"
        done.mkdir()
        (done / ".gitkeep").write_text("")  # Git doesn't track empty dirs

        # Root index
        (board_dir / "index.md").write_text("# My Project Board\n\nBoard description.")

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

    # Add and commit
    repo.git.add("-A")
    repo.index.commit("Initial board")

    return tmp_path


def test_parse_dirname_simple():
    order, name, hidden = _parse_dirname("1.backlog")
    assert order == "1"
    assert name == "Backlog"
    assert hidden is False


def test_parse_dirname_with_dashes():
    order, name, hidden = _parse_dirname("2.in-progress")
    assert order == "2"
    assert name == "In progress"
    assert hidden is False


def test_parse_dirname_hidden():
    order, name, hidden = _parse_dirname(".99.archived")
    assert order == "99"
    assert name == "Archived"
    assert hidden is True


def test_parse_dirname_no_prefix():
    order, name, hidden = _parse_dirname("random-dir")
    assert order is None


def test_parse_dirname_hidden_no_prefix():
    order, name, hidden = _parse_dirname(".all")
    assert order is None
    assert hidden is True


def test_parse_link_name():
    position, slug = _parse_link_name("01.fix-login-bug.md")
    assert position == "01"
    assert slug == "fix-login-bug"


def test_parse_link_name_no_prefix():
    position, slug = _parse_link_name("readme.md")
    assert position is None


@pytest.mark.asyncio
async def test_load_board_cards(sample_board):
    board = await load_board(sample_board)

    assert len(board.cards) == 3
    assert "001" in board.cards
    assert "002" in board.cards
    assert "003" in board.cards

    assert board.cards["001"].content.title == "Fix login bug"
    assert board.cards["003"].content.meta.get("tags") == ["urgent"]


@pytest.mark.asyncio
async def test_load_board_columns(sample_board):
    board = await load_board(sample_board)

    assert len(board.columns) == 3
    assert board.columns[0].name == "Backlog"
    assert board.columns[1].name == "In progress"
    assert board.columns[2].name == "Done"


@pytest.mark.asyncio
async def test_load_board_links(sample_board):
    board = await load_board(sample_board)

    backlog = board.columns[0]
    assert len(backlog.links) == 1
    assert backlog.links[0].card_id == "001"

    doing = board.columns[1]
    assert len(doing.links) == 2
    assert doing.links[0].card_id == "002"
    assert doing.links[1].card_id == "003"


@pytest.mark.asyncio
async def test_load_board_broken_link(sample_board):
    # Add a broken symlink to the repo
    repo = Repo(sample_board)
    backlog = sample_board / "1.backlog"
    (backlog / "99.broken.md").symlink_to("../.all/999.md")
    repo.git.add("-A")
    repo.index.commit("Add broken link")

    board = await load_board(sample_board)

    backlog_col = board.columns[0]
    broken = [link for link in backlog_col.links if link.broken]
    assert len(broken) == 1
    assert broken[0].card_id == "999"


@pytest.mark.asyncio
async def test_load_board_root_content(sample_board):
    board = await load_board(sample_board)

    assert board.content.title == "My Project Board"
    assert board.content.body == "Board description."


@pytest.mark.asyncio
async def test_load_board_commit_set(sample_board):
    board = await load_board(sample_board)

    assert board.commit != ""
    assert len(board.commit) == 40  # SHA length


@pytest.mark.asyncio
async def test_load_board_missing_branch(tmp_path):
    repo = Repo.init(tmp_path)
    (tmp_path / ".gitkeep").write_text("")
    repo.index.add([".gitkeep"])
    repo.index.commit("Initial")

    with pytest.raises(ValueError, match="Branch 'ganban' not found"):
        await load_board(tmp_path)


@pytest.mark.asyncio
async def test_load_board_ignores_non_md_in_all(sample_board):
    """Non-.md files and subdirs in .all/ are ignored."""
    repo = Repo(sample_board)
    all_dir = sample_board / ".all"

    # Add a non-.md file
    (all_dir / "readme.txt").write_text("ignored")
    # Add a subdirectory
    (all_dir / "subdir").mkdir()
    (all_dir / "subdir" / "nested.md").write_text("# Nested\n")

    repo.git.add("-A")
    repo.index.commit("Add non-card items")

    board = await load_board(sample_board)

    # Should still only have the original 3 cards
    assert len(board.cards) == 3
    assert "readme" not in board.cards
    assert "subdir" not in board.cards


@pytest.mark.asyncio
async def test_load_board_ignores_non_symlinks_in_column(sample_board):
    """Regular files, subdirs, and non-.md symlinks in columns are ignored."""
    repo = Repo(sample_board)
    backlog = sample_board / "1.backlog"

    # Add a regular file (not a symlink)
    (backlog / "02.regular-file.md").write_text("# Not a symlink\n")
    # Add a symlink without .md extension
    (backlog / "03.no-extension").symlink_to("../.all/002.md")
    # Add a subdirectory (Tree in git)
    (backlog / "subdir").mkdir()
    (backlog / "subdir" / "nested.md").write_text("# Nested\n")

    repo.git.add("-A")
    repo.index.commit("Add non-symlink items")

    board = await load_board(sample_board)

    # Backlog should only have the original symlink
    assert len(board.columns[0].links) == 1


@pytest.mark.asyncio
async def test_load_board_ignores_invalid_link_names(sample_board):
    """Symlinks without position prefix are ignored."""
    repo = Repo(sample_board)
    backlog = sample_board / "1.backlog"

    # Add symlink without position prefix
    (backlog / "no-position.md").symlink_to("../.all/002.md")

    repo.git.add("-A")
    repo.index.commit("Add invalid link name")

    board = await load_board(sample_board)

    # Backlog should only have the original symlink
    assert len(board.columns[0].links) == 1
