"""Tests for board writer."""

from pathlib import Path

import pytest
from git import Repo

from ganban.loader import load_board
from ganban.models import Board, Card, CardLink, Column, MarkdownDoc
from ganban.writer import (
    MergeRequired,
    check_for_merge,
    check_remote_for_merge,
    create_card,
    create_column,
    save_board,
    slugify,
    try_auto_merge,
)


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
    (all_dir / "001.md").write_text("# First card\n\nDescription.\n")

    backlog = empty_repo / "1.backlog"
    backlog.mkdir()
    (backlog / "01.first-card.md").symlink_to("../.all/001.md")

    repo.git.add("-A")
    repo.index.commit("Initial board")

    return empty_repo


@pytest.mark.asyncio
async def test_save_new_board(empty_repo):
    """Save a board to a fresh repo creates the branch."""
    board = Board(repo_path=str(empty_repo))
    board.cards = {
        "001": Card(
            id="001",
            path=".all/001.md",
            content=MarkdownDoc(title="Test card", body="Body text."),
        ),
    }
    board.columns = [
        Column(
            order="1",
            name="Backlog",
            path="1.backlog",
            links=[
                CardLink(position="01", slug="test-card", card_id="001"),
            ],
        ),
    ]

    new_commit = await save_board(board, message="Create board")

    assert len(new_commit) == 40

    # Verify we can load it back
    loaded = await load_board(empty_repo)
    assert len(loaded.cards) == 1
    assert loaded.cards["001"].content.title == "Test card"
    assert len(loaded.columns) == 1
    assert loaded.columns[0].links[0].card_id == "001"


@pytest.mark.asyncio
async def test_save_updates_existing_board(repo_with_ganban):
    """Save modifications to an existing board."""
    board = await load_board(repo_with_ganban)
    original_commit = board.commit

    # Add a new card
    board.cards["002"] = Card(
        id="002",
        path=".all/002.md",
        content=MarkdownDoc(title="New card", body="New description."),
    )

    # Add a new column with the card
    board.columns.append(
        Column(
            order="2",
            name="Done",
            path="2.done",
            links=[
                CardLink(position="01", slug="new-card", card_id="002"),
            ],
        )
    )

    new_commit = await save_board(board, message="Add card and column")

    assert new_commit != original_commit

    # Verify parent relationship
    repo = Repo(repo_with_ganban)
    commit = repo.commit(new_commit)
    assert commit.parents[0].hexsha == original_commit


@pytest.mark.asyncio
async def test_save_board_with_root_index(empty_repo):
    """Board with root index.md is saved correctly."""
    board = Board(
        repo_path=str(empty_repo),
        content=MarkdownDoc(title="My Board", body="Board description."),
    )
    board.cards = {
        "001": Card(
            id="001",
            content=MarkdownDoc(title="Card"),
        ),
    }
    board.columns = [
        Column(order="1", name="Backlog", path="1.backlog"),
    ]

    await save_board(board)

    loaded = await load_board(empty_repo)
    assert loaded.content.title == "My Board"
    assert loaded.content.body == "Board description."


@pytest.mark.asyncio
async def test_save_board_with_column_index(empty_repo):
    """Column with index.md is saved correctly."""
    board = Board(repo_path=str(empty_repo))
    board.cards = {
        "001": Card(id="001", content=MarkdownDoc(title="Card")),
    }
    board.columns = [
        Column(
            order="1",
            name="Backlog",
            path="1.backlog",
            content=MarkdownDoc(title="Backlog", body="Column description."),
        ),
    ]

    await save_board(board)

    loaded = await load_board(empty_repo)
    assert loaded.columns[0].content.title == "Backlog"
    assert loaded.columns[0].content.body == "Column description."


@pytest.mark.asyncio
async def test_save_preserves_card_metadata(empty_repo):
    """Card front-matter is preserved through save/load cycle."""
    board = Board(repo_path=str(empty_repo))
    board.cards = {
        "001": Card(
            id="001",
            content=MarkdownDoc(
                title="Urgent card",
                body="Fix this ASAP.",
                meta={"tags": ["urgent", "bug"], "priority": 1},
            ),
        ),
    }
    board.columns = [
        Column(order="1", name="Backlog", path="1.backlog"),
    ]

    await save_board(board)

    loaded = await load_board(empty_repo)
    assert loaded.cards["001"].content.meta["tags"] == ["urgent", "bug"]
    assert loaded.cards["001"].content.meta["priority"] == 1


@pytest.mark.asyncio
async def test_save_move_card_between_columns(repo_with_ganban):
    """Moving a card between columns shows up correctly."""
    board = await load_board(repo_with_ganban)

    # Move card from backlog to a new done column
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

    await save_board(board, message="Move card to done")

    loaded = await load_board(repo_with_ganban)
    assert len(loaded.columns[0].links) == 0  # Backlog empty
    assert len(loaded.columns[1].links) == 1  # Done has the card
    assert loaded.columns[1].links[0].card_id == "001"


@pytest.mark.asyncio
async def test_save_delete_card(repo_with_ganban):
    """Deleting a card removes it from .all/"""
    board = await load_board(repo_with_ganban)
    assert "001" in board.cards

    # Remove card and its link
    del board.cards["001"]
    board.columns[0].links = []

    await save_board(board, message="Delete card")

    loaded = await load_board(repo_with_ganban)
    assert "001" not in loaded.cards


@pytest.mark.asyncio
async def test_save_reorder_cards_in_column(empty_repo):
    """Reordering cards updates their position prefixes."""
    board = Board(repo_path=str(empty_repo))
    board.cards = {
        "001": Card(id="001", content=MarkdownDoc(title="First")),
        "002": Card(id="002", content=MarkdownDoc(title="Second")),
        "003": Card(id="003", content=MarkdownDoc(title="Third")),
    }
    board.columns = [
        Column(
            order="1",
            name="Backlog",
            path="1.backlog",
            links=[
                CardLink(position="01", slug="first", card_id="001"),
                CardLink(position="02", slug="second", card_id="002"),
                CardLink(position="03", slug="third", card_id="003"),
            ],
        ),
    ]

    await save_board(board)

    # Reorder: move third to first position
    board = await load_board(empty_repo)
    links = board.columns[0].links
    links[0].position = "02"
    links[1].position = "03"
    links[2].position = "01"

    await save_board(board, message="Reorder cards")

    loaded = await load_board(empty_repo)
    positions = [(link.position, link.card_id) for link in loaded.columns[0].links]
    assert positions == [("01", "003"), ("02", "001"), ("03", "002")]


@pytest.mark.asyncio
async def test_save_empty_column(empty_repo):
    """Empty columns are saved correctly."""
    board = Board(repo_path=str(empty_repo))
    board.cards = {}
    board.columns = [
        Column(order="1", name="Backlog", path="1.backlog"),
        Column(order="2", name="Done", path="2.done"),
    ]

    await save_board(board)

    loaded = await load_board(empty_repo)
    assert len(loaded.columns) == 2
    assert all(len(c.links) == 0 for c in loaded.columns)


@pytest.mark.asyncio
async def test_save_returns_valid_commit(empty_repo):
    """The returned commit hash is valid and points to correct tree."""
    board = Board(repo_path=str(empty_repo))
    board.cards = {
        "001": Card(id="001", content=MarkdownDoc(title="Test")),
    }
    board.columns = [
        Column(order="1", name="Backlog", path="1.backlog"),
    ]

    commit_sha = await save_board(board)

    repo = Repo(empty_repo)
    commit = repo.commit(commit_sha)
    assert commit.message.strip() == "Update board"
    assert ".all" in commit.tree
    assert "1.backlog" in commit.tree


@pytest.mark.asyncio
async def test_save_custom_branch(empty_repo):
    """Can save to a custom branch name."""
    board = Board(repo_path=str(empty_repo))
    board.cards = {
        "001": Card(id="001", content=MarkdownDoc(title="Test")),
    }
    board.columns = [
        Column(order="1", name="Backlog", path="1.backlog"),
    ]

    await save_board(board, branch="my-board")

    # Should fail on default branch
    with pytest.raises(ValueError, match="Branch 'ganban' not found"):
        await load_board(empty_repo)

    # Should load from custom branch
    loaded = await load_board(empty_repo, branch="my-board")
    assert len(loaded.cards) == 1


@pytest.mark.asyncio
async def test_save_with_explicit_parents(repo_with_ganban):
    """Can save with explicit parent commits for merge."""
    board = await load_board(repo_with_ganban)
    first_commit = board.commit

    # Make a change and save
    board.cards["001"].content.body = "Changed"
    second_commit = await save_board(board)

    # Now create a "merge" commit with both as parents
    board = await load_board(repo_with_ganban)
    board.cards["001"].content.body = "Merged"
    merge_commit = await save_board(board, message="Merge", parents=[first_commit, second_commit])

    repo = Repo(repo_with_ganban)
    commit = repo.commit(merge_commit)
    assert len(commit.parents) == 2


# --- Merge detection tests ---


@pytest.mark.asyncio
async def test_check_for_merge_no_changes(repo_with_ganban):
    """No merge needed when branch hasn't moved."""
    board = await load_board(repo_with_ganban)

    result = check_for_merge(board)

    assert result is None


@pytest.mark.asyncio
async def test_check_for_merge_branch_moved(repo_with_ganban):
    """Merge needed when branch has moved."""
    board = await load_board(repo_with_ganban)
    original_commit = board.commit

    # External change moves the branch
    repo = Repo(repo_with_ganban)
    repo.git.checkout("ganban")
    all_dir = repo_with_ganban / ".all"
    (all_dir / "002.md").write_text("# External card\n")
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
    board.cards = {"001": Card(id="001", content=MarkdownDoc(title="Test"))}
    board.columns = [Column(order="1", name="Backlog", path="1.backlog")]

    result = check_for_merge(board)

    assert result is None


def test_check_for_merge_no_board_commit(repo_with_ganban):
    """No merge check when board has no commit (fresh board)."""
    board = Board(repo_path=str(repo_with_ganban))
    # board.commit is empty string (default)

    result = check_for_merge(board)

    assert result is None


@pytest.mark.asyncio
async def test_check_for_merge_unrelated_histories(repo_with_ganban):
    """No merge when histories have no common ancestor."""
    # Load board from existing ganban branch
    board = await load_board(repo_with_ganban)

    # Create a new orphan branch (unrelated history)
    repo = Repo(repo_with_ganban)
    repo.git.checkout("--orphan", "unrelated")
    repo.git.rm("-rf", ".", "--cached")
    repo.git.clean("-fd")

    all_dir = repo_with_ganban / ".all"
    all_dir.mkdir()
    (all_dir / "999.md").write_text("# Unrelated card\n")
    backlog = repo_with_ganban / "1.backlog"
    backlog.mkdir()

    repo.git.add("-A")
    repo.index.commit("Unrelated commit")

    # Update ganban ref to point to unrelated branch
    unrelated_commit = repo.head.commit.hexsha
    repo.git.update_ref("refs/heads/ganban", unrelated_commit)

    # Now check_for_merge should find no common ancestor
    result = check_for_merge(board)

    assert result is None  # No common ancestor


# --- Auto-merge tests ---


@pytest.mark.asyncio
async def test_auto_merge_clean(repo_with_ganban):
    """Auto-merge succeeds when different files changed."""
    board = await load_board(repo_with_ganban)
    original_commit = board.commit

    # External change: add new card
    repo = Repo(repo_with_ganban)
    repo.git.checkout("ganban")
    all_dir = repo_with_ganban / ".all"
    (all_dir / "002.md").write_text("# External card\n\nAdded externally.\n")
    repo.git.add("-A")
    external_commit = repo.index.commit("Add external card").hexsha

    # Our change: edit card 001
    board.cards["001"].content.body = "Modified description."

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
    loaded = await load_board(repo_with_ganban)
    assert loaded.cards["001"].content.body == "Modified description."
    assert "002" in loaded.cards


@pytest.mark.asyncio
async def test_auto_merge_conflict(repo_with_ganban):
    """Auto-merge fails when same file changed."""
    board = await load_board(repo_with_ganban)

    # External change: edit card 001
    repo = Repo(repo_with_ganban)
    repo.git.checkout("ganban")
    all_dir = repo_with_ganban / ".all"
    (all_dir / "001.md").write_text("# First card\n\nExternal edit.\n")
    repo.git.add("-A")
    repo.index.commit("External edit")

    # Our change: also edit card 001
    board.cards["001"].content.body = "Our edit."

    # Check and try auto-merge
    merge_info = check_for_merge(board)
    assert merge_info is not None

    result = try_auto_merge(board, merge_info)
    assert result is None  # Conflict, auto-merge failed


@pytest.mark.asyncio
async def test_manual_merge_after_conflict(repo_with_ganban):
    """Manual merge resolution flow."""
    board = await load_board(repo_with_ganban)
    ours_commit = board.commit

    # External change
    repo = Repo(repo_with_ganban)
    repo.git.checkout("ganban")
    all_dir = repo_with_ganban / ".all"
    (all_dir / "001.md").write_text("# First card\n\nExternal edit.\n")
    repo.git.add("-A")
    theirs_commit = repo.index.commit("External edit").hexsha

    # Our change conflicts
    board.cards["001"].content.body = "Our edit."

    # Check for merge
    merge_info = check_for_merge(board)
    assert merge_info is not None

    # Auto-merge fails
    assert try_auto_merge(board, merge_info) is None

    # Manual resolution: UI would load all 3 boards and let user resolve
    # base_board = await load_board(repo_with_ganban, commit=merge_info.base)
    # ours_board = await load_board(repo_with_ganban, commit=merge_info.ours)
    # theirs_board = await load_board(repo_with_ganban, commit=merge_info.theirs)
    # ... user picks resolution ...

    # Save resolved board with both parents
    board.cards["001"].content.body = "Manually resolved."
    new_commit = await save_board(
        board,
        message="Resolve conflict",
        parents=[ours_commit, theirs_commit],
    )

    # Verify merge commit
    commit = repo.commit(new_commit)
    assert len(commit.parents) == 2

    loaded = await load_board(repo_with_ganban)
    assert loaded.cards["001"].content.body == "Manually resolved."


# --- Remote merge tests ---


@pytest.fixture
def repo_with_remote(tmp_path):
    """Create a repo with a ganban branch and a 'remote' repo."""
    # Create the "remote" repo (bare)
    remote_path = tmp_path / "remote.git"
    Repo.init(remote_path, bare=True)

    # Create local repo
    local_path = tmp_path / "local"
    local_path.mkdir()
    local_repo = Repo.init(local_path)

    # Initial commit on main
    (local_path / ".gitkeep").write_text("")
    local_repo.index.add([".gitkeep"])
    local_repo.index.commit("Initial commit")

    # Create ganban branch with content
    local_repo.git.checkout("--orphan", "ganban")
    local_repo.git.rm("-rf", ".", "--cached")
    local_repo.git.clean("-fd")

    all_dir = local_path / ".all"
    all_dir.mkdir()
    (all_dir / "001.md").write_text("# First card\n\nDescription.\n")

    backlog = local_path / "1.backlog"
    backlog.mkdir()
    (backlog / "01.first-card.md").symlink_to("../.all/001.md")

    local_repo.git.add("-A")
    local_repo.index.commit("Initial board")

    # Add remote and push
    local_repo.create_remote("origin", str(remote_path))
    local_repo.git.push("origin", "ganban")

    return local_path, remote_path


@pytest.mark.asyncio
async def test_check_remote_no_changes(repo_with_remote):
    """No merge needed when remote hasn't changed."""
    local_path, _ = repo_with_remote
    board = await load_board(local_path)

    result = check_remote_for_merge(board, remote="origin")

    assert result is None


def test_check_remote_no_board_commit(repo_with_remote):
    """No merge check when board has no commit."""
    local_path, _ = repo_with_remote
    board = Board(repo_path=str(local_path))
    # board.commit is empty

    result = check_remote_for_merge(board, remote="origin")

    assert result is None


@pytest.mark.asyncio
async def test_check_remote_tracking_branch_missing(repo_with_ganban):
    """No merge when remote tracking branch doesn't exist."""
    board = await load_board(repo_with_ganban)

    # No remote configured, so origin/ganban doesn't exist
    result = check_remote_for_merge(board, remote="origin")

    assert result is None


@pytest.mark.asyncio
async def test_check_remote_unrelated_histories(repo_with_remote):
    """No merge when remote has unrelated history."""
    local_path, remote_path = repo_with_remote
    board = await load_board(local_path)

    # Create unrelated history on remote by creating a fresh repo,
    # adding content, and pushing to the remote
    import tempfile

    with tempfile.TemporaryDirectory() as other_path:
        # Initialize fresh repo (unrelated history)
        other_repo = Repo.init(other_path)

        all_dir = Path(other_path) / ".all"
        all_dir.mkdir()
        (all_dir / "999.md").write_text("# Unrelated\n")
        backlog = Path(other_path) / "1.backlog"
        backlog.mkdir()
        (backlog / ".gitkeep").write_text("")

        other_repo.git.add("-A")
        other_repo.index.commit("Unrelated history")

        # Add remote and force push to replace ganban branch
        other_repo.create_remote("origin", str(remote_path))
        other_repo.git.push("origin", "HEAD:ganban", "--force")

    # Fetch the new unrelated history
    local_repo = Repo(local_path)
    local_repo.remotes.origin.fetch()

    # Now check_remote_for_merge should find no common ancestor
    result = check_remote_for_merge(board, remote="origin")

    assert result is None


@pytest.mark.asyncio
async def test_check_remote_has_changes(repo_with_remote):
    """Merge needed when remote has new commits."""
    local_path, remote_path = repo_with_remote
    board = await load_board(local_path)
    original_commit = board.commit

    # Simulate someone else pushing to the remote
    # Clone to a temp location, make changes, push
    import tempfile

    with tempfile.TemporaryDirectory() as other_path:
        other_repo = Repo.clone_from(str(remote_path), other_path)
        other_repo.git.checkout("ganban")

        all_dir = Path(other_path) / ".all"
        (all_dir / "002.md").write_text("# Remote card\n\nAdded by someone else.\n")
        other_repo.git.add("-A")
        other_repo.index.commit("Add card from remote")
        other_repo.git.push("origin", "ganban")

    # Fetch in local repo
    local_repo = Repo(local_path)
    local_repo.remotes.origin.fetch()

    # Check for remote merge
    result = check_remote_for_merge(board, remote="origin")

    assert result is not None
    assert isinstance(result, MergeRequired)
    assert result.ours == original_commit
    assert result.theirs != original_commit
    assert result.base == original_commit


@pytest.mark.asyncio
async def test_check_remote_we_are_ahead(repo_with_remote):
    """No merge needed when we are ahead of remote."""
    local_path, _ = repo_with_remote
    board = await load_board(local_path)

    # Make a local change (don't push)
    board.cards["001"].content.body = "Local change."
    await save_board(board)

    # Reload and check
    board = await load_board(local_path)
    result = check_remote_for_merge(board, remote="origin")

    assert result is None  # Remote is behind, nothing to merge


@pytest.mark.asyncio
async def test_remote_auto_merge(repo_with_remote):
    """Full flow: fetch, check, auto-merge from remote."""
    local_path, remote_path = repo_with_remote
    board = await load_board(local_path)

    # Make local change
    board.cards["001"].content.body = "Local edit."

    # Simulate remote change (different file)
    import tempfile

    with tempfile.TemporaryDirectory() as other_path:
        other_repo = Repo.clone_from(str(remote_path), other_path)
        other_repo.git.checkout("ganban")

        all_dir = Path(other_path) / ".all"
        (all_dir / "002.md").write_text("# Remote card\n")
        other_repo.git.add("-A")
        other_repo.index.commit("Add card from remote")
        other_repo.git.push("origin", "ganban")

    # Fetch
    local_repo = Repo(local_path)
    local_repo.remotes.origin.fetch()

    # Check for merge
    merge_info = check_remote_for_merge(board, remote="origin")
    assert merge_info is not None

    # Auto-merge should succeed (different files)
    new_commit = try_auto_merge(board, merge_info, message="Merge remote")
    assert new_commit is not None

    # Both changes present
    loaded = await load_board(local_path)
    assert loaded.cards["001"].content.body == "Local edit."
    assert "002" in loaded.cards


# --- create_card tests ---


@pytest.mark.asyncio
async def test_create_card_basic(repo_with_ganban):
    """Create a card with default options."""
    board = await load_board(repo_with_ganban)
    original_count = len(board.cards)

    card = create_card(board, "New card", "Description here")

    assert card.id == "2"  # Next after 001
    assert card.content.title == "New card"
    assert card.content.body == "Description here"
    assert card.id in board.cards
    assert len(board.cards) == original_count + 1

    # Should be added to first column
    assert board.columns[0].links[-1].card_id == "2"


@pytest.mark.asyncio
async def test_create_card_specific_column(repo_with_ganban):
    """Create a card in a specific column."""
    board = await load_board(repo_with_ganban)
    # Add a second column first
    doing_column = create_column(board, "Doing")

    card = create_card(board, "In progress card", column=doing_column)

    assert card.id in board.cards
    assert doing_column.links[-1].card_id == card.id


@pytest.mark.asyncio
async def test_create_card_specific_position(repo_with_ganban):
    """Create a card at a specific position in column."""
    board = await load_board(repo_with_ganban)
    backlog = board.columns[0]
    original_first = backlog.links[0].card_id

    card = create_card(board, "Top priority", column=backlog, position=0)

    assert backlog.links[0].card_id == card.id
    assert backlog.links[1].card_id == original_first


def test_create_card_empty_board(empty_repo):
    """Create a card on an empty board."""
    board = Board(repo_path=str(empty_repo))
    board.columns = [Column(order="1", name="Backlog", path="1.backlog")]

    card = create_card(board, "First card")

    assert card.id == "001"
    assert card.id in board.cards
    assert board.columns[0].links[0].card_id == "001"


@pytest.mark.asyncio
async def test_create_card_saves(repo_with_ganban):
    """Created cards persist after save."""
    board = await load_board(repo_with_ganban)

    card = create_card(board, "Persistent card", "Will be saved")
    await save_board(board)

    loaded = await load_board(repo_with_ganban)
    assert card.id in loaded.cards
    assert loaded.cards[card.id].content.title == "Persistent card"


# --- create_column tests ---


@pytest.mark.asyncio
async def test_create_column_basic(repo_with_ganban):
    """Create a column with default order."""
    board = await load_board(repo_with_ganban)
    original_count = len(board.columns)

    column = create_column(board, "Archive")

    assert column.name == "Archive"
    assert column.order == "2"  # After 1 (backlog)
    assert column.path == "2.archive"
    assert column.hidden is False
    assert len(board.columns) == original_count + 1


@pytest.mark.asyncio
async def test_create_column_specific_order(repo_with_ganban):
    """Create a column with specific order."""
    board = await load_board(repo_with_ganban)

    column = create_column(board, "Priority", order="0")

    assert column.order == "0"
    assert column.path == "0.priority"
    # Should be sorted to first position
    assert board.columns[0].order == "0"


@pytest.mark.asyncio
async def test_create_column_hidden(repo_with_ganban):
    """Create a hidden column."""
    board = await load_board(repo_with_ganban)

    column = create_column(board, "Hidden", hidden=True)

    assert column.hidden is True
    assert column.path.startswith(".")


def test_create_column_empty_board(empty_repo):
    """Create first column on empty board."""
    board = Board(repo_path=str(empty_repo))

    column = create_column(board, "Backlog")

    assert column.order == "1"
    assert len(board.columns) == 1


@pytest.mark.asyncio
async def test_create_column_saves(repo_with_ganban):
    """Created columns persist after save."""
    board = await load_board(repo_with_ganban)

    create_column(board, "Archive")
    await save_board(board)

    loaded = await load_board(repo_with_ganban)
    assert any(c.name == "Archive" for c in loaded.columns)


def test_slugify_basic():
    """Basic slugification."""
    assert slugify("Hello World") == "hello-world"


def test_slugify_special_chars():
    """Special characters become hyphens."""
    assert slugify("What: is this?") == "what-is-this"
    assert slugify("Test!") == "test"
    assert slugify("{foo}") == "foo"
    assert slugify("a.b.c") == "a-b-c"


def test_slugify_multiple_spaces():
    """Multiple spaces/special chars collapse to single hyphen."""
    assert slugify("hello    world") == "hello-world"
    assert slugify("a - b - c") == "a-b-c"


def test_slugify_leading_trailing():
    """Leading/trailing special chars stripped."""
    assert slugify("  hello  ") == "hello"
    assert slugify("---test---") == "test"
    assert slugify("!hello!") == "hello"


def test_slugify_empty():
    """Empty string returns 'untitled'."""
    assert slugify("") == "untitled"
    assert slugify("   ") == "untitled"
    assert slugify("!!!") == "untitled"
