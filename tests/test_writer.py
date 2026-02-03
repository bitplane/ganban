"""Tests for board writer."""

import pytest
from git import Repo

from ganban.loader import load_board
from ganban.models import Board, Column, MarkdownDoc, Ticket, TicketLink
from ganban.writer import MergeRequired, check_for_merge, save_board, try_auto_merge


@pytest.fixture
def empty_repo(tmp_path):
    """Create an empty git repo."""
    repo = Repo.init(tmp_path)
    (tmp_path / ".gitkeep").write_text("")
    repo.index.add([".gitkeep"])
    repo.index.commit("Initial commit")
    return tmp_path


@pytest.fixture
def repo_with_ganban(empty_repo):
    """Create a repo with an existing ganban branch."""
    repo = Repo(empty_repo)

    # Create orphan ganban branch with minimal content
    repo.git.checkout("--orphan", "ganban")
    repo.git.rm("-rf", ".", "--cached")
    repo.git.clean("-fd")

    all_dir = empty_repo / ".all"
    all_dir.mkdir()
    (all_dir / "001.md").write_text("# First ticket\n\nDescription.\n")

    backlog = empty_repo / "1.backlog"
    backlog.mkdir()
    (backlog / "01.first-ticket.md").symlink_to("../.all/001.md")

    repo.git.add("-A")
    repo.index.commit("Initial board")

    return empty_repo


def test_save_new_board(empty_repo):
    """Save a board to a fresh repo creates the branch."""
    board = Board(repo_path=str(empty_repo))
    board.tickets = {
        "001": Ticket(
            id="001",
            path=".all/001.md",
            content=MarkdownDoc(title="Test ticket", body="Body text."),
        ),
    }
    board.columns = [
        Column(
            order="1",
            name="Backlog",
            path="1.backlog",
            links=[
                TicketLink(position="01", slug="test-ticket", ticket_id="001"),
            ],
        ),
    ]

    new_commit = save_board(board, message="Create board")

    assert len(new_commit) == 40

    # Verify we can load it back
    loaded = load_board(empty_repo)
    assert len(loaded.tickets) == 1
    assert loaded.tickets["001"].content.title == "Test ticket"
    assert len(loaded.columns) == 1
    assert loaded.columns[0].links[0].ticket_id == "001"


def test_save_updates_existing_board(repo_with_ganban):
    """Save modifications to an existing board."""
    board = load_board(repo_with_ganban)
    original_commit = board.commit

    # Add a new ticket
    board.tickets["002"] = Ticket(
        id="002",
        path=".all/002.md",
        content=MarkdownDoc(title="New ticket", body="New description."),
    )

    # Add a new column with the ticket
    board.columns.append(
        Column(
            order="2",
            name="Done",
            path="2.done",
            links=[
                TicketLink(position="01", slug="new-ticket", ticket_id="002"),
            ],
        )
    )

    new_commit = save_board(board, message="Add ticket and column")

    assert new_commit != original_commit

    # Verify parent relationship
    repo = Repo(repo_with_ganban)
    commit = repo.commit(new_commit)
    assert commit.parents[0].hexsha == original_commit


def test_save_board_with_root_index(empty_repo):
    """Board with root index.md is saved correctly."""
    board = Board(
        repo_path=str(empty_repo),
        content=MarkdownDoc(title="My Board", body="Board description."),
    )
    board.tickets = {
        "001": Ticket(
            id="001",
            content=MarkdownDoc(title="Ticket"),
        ),
    }
    board.columns = [
        Column(order="1", name="Backlog", path="1.backlog"),
    ]

    save_board(board)

    loaded = load_board(empty_repo)
    assert loaded.content.title == "My Board"
    assert loaded.content.body == "Board description."


def test_save_board_with_column_index(empty_repo):
    """Column with index.md is saved correctly."""
    board = Board(repo_path=str(empty_repo))
    board.tickets = {
        "001": Ticket(id="001", content=MarkdownDoc(title="Ticket")),
    }
    board.columns = [
        Column(
            order="1",
            name="Backlog",
            path="1.backlog",
            content=MarkdownDoc(title="Backlog", body="Column description."),
        ),
    ]

    save_board(board)

    loaded = load_board(empty_repo)
    assert loaded.columns[0].content.title == "Backlog"
    assert loaded.columns[0].content.body == "Column description."


def test_save_preserves_ticket_metadata(empty_repo):
    """Ticket front-matter is preserved through save/load cycle."""
    board = Board(repo_path=str(empty_repo))
    board.tickets = {
        "001": Ticket(
            id="001",
            content=MarkdownDoc(
                title="Urgent ticket",
                body="Fix this ASAP.",
                meta={"tags": ["urgent", "bug"], "priority": 1},
            ),
        ),
    }
    board.columns = [
        Column(order="1", name="Backlog", path="1.backlog"),
    ]

    save_board(board)

    loaded = load_board(empty_repo)
    assert loaded.tickets["001"].content.meta["tags"] == ["urgent", "bug"]
    assert loaded.tickets["001"].content.meta["priority"] == 1


def test_save_move_ticket_between_columns(repo_with_ganban):
    """Moving a ticket between columns shows up correctly."""
    board = load_board(repo_with_ganban)

    # Move ticket from backlog to a new done column
    link = board.columns[0].links.pop(0)
    link.position = "01"

    board.columns.append(
        Column(
            order="2",
            name="Done",
            path="2.done",
            links=[link],
        )
    )

    save_board(board, message="Move ticket to done")

    loaded = load_board(repo_with_ganban)
    assert len(loaded.columns[0].links) == 0  # Backlog empty
    assert len(loaded.columns[1].links) == 1  # Done has the ticket
    assert loaded.columns[1].links[0].ticket_id == "001"


def test_save_delete_ticket(repo_with_ganban):
    """Deleting a ticket removes it from .all/"""
    board = load_board(repo_with_ganban)
    assert "001" in board.tickets

    # Remove ticket and its link
    del board.tickets["001"]
    board.columns[0].links = []

    save_board(board, message="Delete ticket")

    loaded = load_board(repo_with_ganban)
    assert "001" not in loaded.tickets


def test_save_reorder_tickets_in_column(empty_repo):
    """Reordering tickets updates their position prefixes."""
    board = Board(repo_path=str(empty_repo))
    board.tickets = {
        "001": Ticket(id="001", content=MarkdownDoc(title="First")),
        "002": Ticket(id="002", content=MarkdownDoc(title="Second")),
        "003": Ticket(id="003", content=MarkdownDoc(title="Third")),
    }
    board.columns = [
        Column(
            order="1",
            name="Backlog",
            path="1.backlog",
            links=[
                TicketLink(position="01", slug="first", ticket_id="001"),
                TicketLink(position="02", slug="second", ticket_id="002"),
                TicketLink(position="03", slug="third", ticket_id="003"),
            ],
        ),
    ]

    save_board(board)

    # Reorder: move third to first position
    board = load_board(empty_repo)
    links = board.columns[0].links
    links[0].position = "02"
    links[1].position = "03"
    links[2].position = "01"

    save_board(board, message="Reorder tickets")

    loaded = load_board(empty_repo)
    positions = [(link.position, link.ticket_id) for link in loaded.columns[0].links]
    assert positions == [("01", "003"), ("02", "001"), ("03", "002")]


def test_save_empty_column(empty_repo):
    """Empty columns are saved correctly."""
    board = Board(repo_path=str(empty_repo))
    board.tickets = {}
    board.columns = [
        Column(order="1", name="Backlog", path="1.backlog"),
        Column(order="2", name="Done", path="2.done"),
    ]

    save_board(board)

    loaded = load_board(empty_repo)
    assert len(loaded.columns) == 2
    assert all(len(c.links) == 0 for c in loaded.columns)


def test_save_returns_valid_commit(empty_repo):
    """The returned commit hash is valid and points to correct tree."""
    board = Board(repo_path=str(empty_repo))
    board.tickets = {
        "001": Ticket(id="001", content=MarkdownDoc(title="Test")),
    }
    board.columns = [
        Column(order="1", name="Backlog", path="1.backlog"),
    ]

    commit_sha = save_board(board)

    repo = Repo(empty_repo)
    commit = repo.commit(commit_sha)
    assert commit.message.strip() == "Update board"
    assert ".all" in commit.tree
    assert "1.backlog" in commit.tree


def test_save_custom_branch(empty_repo):
    """Can save to a custom branch name."""
    board = Board(repo_path=str(empty_repo))
    board.tickets = {
        "001": Ticket(id="001", content=MarkdownDoc(title="Test")),
    }
    board.columns = [
        Column(order="1", name="Backlog", path="1.backlog"),
    ]

    save_board(board, branch="my-board")

    # Should fail on default branch
    with pytest.raises(ValueError, match="Branch 'ganban' not found"):
        load_board(empty_repo)

    # Should load from custom branch
    loaded = load_board(empty_repo, branch="my-board")
    assert len(loaded.tickets) == 1


def test_save_with_explicit_parents(repo_with_ganban):
    """Can save with explicit parent commits for merge."""
    board = load_board(repo_with_ganban)
    first_commit = board.commit

    # Make a change and save
    board.tickets["001"].content.body = "Changed"
    second_commit = save_board(board)

    # Now create a "merge" commit with both as parents
    board = load_board(repo_with_ganban)
    board.tickets["001"].content.body = "Merged"
    merge_commit = save_board(board, message="Merge", parents=[first_commit, second_commit])

    repo = Repo(repo_with_ganban)
    commit = repo.commit(merge_commit)
    assert len(commit.parents) == 2


# --- Merge detection tests ---


def test_check_for_merge_no_changes(repo_with_ganban):
    """No merge needed when branch hasn't moved."""
    board = load_board(repo_with_ganban)

    result = check_for_merge(board)

    assert result is None


def test_check_for_merge_branch_moved(repo_with_ganban):
    """Merge needed when branch has moved."""
    board = load_board(repo_with_ganban)
    original_commit = board.commit

    # External change moves the branch
    repo = Repo(repo_with_ganban)
    repo.git.checkout("ganban")
    all_dir = repo_with_ganban / ".all"
    (all_dir / "002.md").write_text("# External ticket\n")
    repo.git.add("-A")
    external_commit = repo.index.commit("External change").hexsha

    # Check for merge
    result = check_for_merge(board)

    assert result is not None
    assert isinstance(result, MergeRequired)
    assert result.ours == original_commit
    assert result.theirs == external_commit
    assert result.base == original_commit  # base is the common ancestor


def test_check_for_merge_new_branch(empty_repo):
    """No merge needed for new branch."""
    board = Board(repo_path=str(empty_repo))
    board.tickets = {"001": Ticket(id="001", content=MarkdownDoc(title="Test"))}
    board.columns = [Column(order="1", name="Backlog", path="1.backlog")]

    result = check_for_merge(board)

    assert result is None


# --- Auto-merge tests ---


def test_auto_merge_clean(repo_with_ganban):
    """Auto-merge succeeds when different files changed."""
    board = load_board(repo_with_ganban)
    original_commit = board.commit

    # External change: add new ticket
    repo = Repo(repo_with_ganban)
    repo.git.checkout("ganban")
    all_dir = repo_with_ganban / ".all"
    (all_dir / "002.md").write_text("# External ticket\n\nAdded externally.\n")
    repo.git.add("-A")
    external_commit = repo.index.commit("Add external ticket").hexsha

    # Our change: edit ticket 001
    board.tickets["001"].content.body = "Modified description."

    # Check and auto-merge
    merge_info = check_for_merge(board)
    assert merge_info is not None

    new_commit = try_auto_merge(board, merge_info, message="Auto-merge")
    assert new_commit is not None

    # Should be a merge commit with two parents
    commit = repo.commit(new_commit)
    assert len(commit.parents) == 2
    parent_shas = {p.hexsha for p in commit.parents}
    assert original_commit in parent_shas
    assert external_commit in parent_shas

    # Both changes should be present
    loaded = load_board(repo_with_ganban)
    assert loaded.tickets["001"].content.body == "Modified description."
    assert "002" in loaded.tickets


def test_auto_merge_conflict(repo_with_ganban):
    """Auto-merge fails when same file changed."""
    board = load_board(repo_with_ganban)

    # External change: edit ticket 001
    repo = Repo(repo_with_ganban)
    repo.git.checkout("ganban")
    all_dir = repo_with_ganban / ".all"
    (all_dir / "001.md").write_text("# First ticket\n\nExternal edit.\n")
    repo.git.add("-A")
    repo.index.commit("External edit")

    # Our change: also edit ticket 001
    board.tickets["001"].content.body = "Our edit."

    # Check and try auto-merge
    merge_info = check_for_merge(board)
    assert merge_info is not None

    result = try_auto_merge(board, merge_info)
    assert result is None  # Conflict, auto-merge failed


def test_manual_merge_after_conflict(repo_with_ganban):
    """Manual merge resolution flow."""
    board = load_board(repo_with_ganban)
    ours_commit = board.commit

    # External change
    repo = Repo(repo_with_ganban)
    repo.git.checkout("ganban")
    all_dir = repo_with_ganban / ".all"
    (all_dir / "001.md").write_text("# First ticket\n\nExternal edit.\n")
    repo.git.add("-A")
    theirs_commit = repo.index.commit("External edit").hexsha

    # Our change conflicts
    board.tickets["001"].content.body = "Our edit."

    # Check for merge
    merge_info = check_for_merge(board)
    assert merge_info is not None

    # Auto-merge fails
    assert try_auto_merge(board, merge_info) is None

    # Manual resolution: UI would load all 3 boards and let user resolve
    # base_board = load_board(repo_with_ganban, commit=merge_info.base)
    # ours_board = load_board(repo_with_ganban, commit=merge_info.ours)
    # theirs_board = load_board(repo_with_ganban, commit=merge_info.theirs)
    # ... user picks resolution ...

    # Save resolved board with both parents
    board.tickets["001"].content.body = "Manually resolved."
    new_commit = save_board(
        board,
        message="Resolve conflict",
        parents=[ours_commit, theirs_commit],
    )

    # Verify merge commit
    commit = repo.commit(new_commit)
    assert len(commit.parents) == 2

    loaded = load_board(repo_with_ganban)
    assert loaded.tickets["001"].content.body == "Manually resolved."
