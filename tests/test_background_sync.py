"""Tests for the background sync engine (ganban.sync)."""

import tempfile

import pytest
from git import Repo

from ganban.model.card import create_card
from ganban.model.column import create_column
from ganban.model.loader import load_board
from ganban.model.node import ListNode, Node
from ganban.model.writer import save_board
from ganban.sync import run_sync_cycle


def _make_board_and_save(repo_path):
    """Create a minimal ganban board and save it."""
    board = Node(repo_path=str(repo_path))
    board.sections = ListNode()
    board.sections["Test Board"] = ""
    board.meta = {}
    board.cards = ListNode()
    board.columns = ListNode()
    create_column(board, "Backlog", order="1")
    create_card(board, "First card", "Description.", column=board.columns["1"])
    save_board(board, message="Initialize board")
    return board


def _init_sync_state(board, local=True, remote=True):
    """Attach transient sync state and config to a board node."""
    if not board.git:
        board.git = Node()
    board.git.sync = Node(status="idle")
    board.git.config = Node(sync_local=local, sync_remote=remote, sync_interval=30)


@pytest.fixture
def local_repo(tmp_path):
    """Create a local repo with a ganban board."""
    repo_path = tmp_path / "local"
    repo_path.mkdir()
    repo = Repo.init(repo_path)
    (repo_path / ".gitkeep").write_text("")
    repo.index.add([".gitkeep"])
    repo.index.commit("Initial commit")
    _make_board_and_save(repo_path)
    return repo_path


@pytest.fixture
def synced_repos(tmp_path):
    """Create a local repo + bare remote, both with ganban branch."""
    remote_path = tmp_path / "remote.git"
    Repo.init(remote_path, bare=True)

    local_path = tmp_path / "local"
    local_path.mkdir()
    local_repo = Repo.init(local_path)
    (local_path / ".gitkeep").write_text("")
    local_repo.index.add([".gitkeep"])
    local_repo.index.commit("Initial commit")

    _make_board_and_save(local_path)

    local_repo.create_remote("origin", str(remote_path))
    local_repo.git.push("origin", "ganban")

    return local_path, remote_path


# --- both toggles off ---


@pytest.mark.asyncio
async def test_sync_both_off_noop(local_repo):
    """Both toggles off, nothing happens."""
    board = load_board(str(local_repo))
    _init_sync_state(board, local=False, remote=False)
    old_commit = board.commit

    await run_sync_cycle(board)

    assert board.commit == old_commit
    assert board.git.sync.status == "idle"


# --- local only ---


@pytest.mark.asyncio
async def test_sync_local_only(local_repo):
    """Local sync saves any pending changes as a new commit."""
    board = load_board(str(local_repo))
    _init_sync_state(board, local=True, remote=False)

    # Make a change
    create_card(board, "New card", "Body.")

    await run_sync_cycle(board)

    assert board.git.sync.status == "idle"
    # Verify the new card persisted
    reloaded = load_board(str(local_repo))
    assert len(reloaded.cards) == 2


# --- remote merge ---


@pytest.mark.asyncio
async def test_sync_remote_merge(synced_repos):
    """Remote changes are fetched, merged, and pushed."""
    local_path, remote_path = synced_repos

    # Push a card from another clone
    with tempfile.TemporaryDirectory() as other_path:
        other_repo = Repo.clone_from(str(remote_path), other_path)
        other_repo.git.checkout("ganban")
        other_board = load_board(other_path)
        sections = ListNode()
        sections["Remote card"] = "Added remotely."
        other_board.cards["r01"] = Node(sections=sections, meta={}, file_path=".all/r01.md")
        col = list(other_board.columns)[0]
        col.links = list(col.links) + ["r01"]
        save_board(other_board, message="Add remote card")
        other_repo.git.push("origin", "ganban")

    board = load_board(str(local_path))
    _init_sync_state(board, local=True, remote=True)

    await run_sync_cycle(board)

    assert board.git.sync.status == "idle"
    assert len(board.cards) == 2


# --- conflict ---


@pytest.mark.asyncio
async def test_sync_conflict_sets_status(synced_repos):
    """Same file edited both sides → status becomes 'conflict'."""
    local_path, remote_path = synced_repos

    # Remote edits card 001
    with tempfile.TemporaryDirectory() as other_path:
        other_repo = Repo.clone_from(str(remote_path), other_path)
        other_repo.git.checkout("ganban")
        other_board = load_board(other_path)
        other_board.cards["001"].sections["First card"] = "Remote edit."
        save_board(other_board, message="Remote edit")
        other_repo.git.push("origin", "ganban")

    # Local edits card 001
    board = load_board(str(local_path))
    board.cards["001"].sections["First card"] = "Local edit."
    save_board(board, message="Local edit")

    # Reload so commit is fresh
    board = load_board(str(local_path))
    _init_sync_state(board, local=True, remote=True)

    await run_sync_cycle(board)

    assert board.git.sync.status == "conflict"


# --- git node survives update ---


@pytest.mark.asyncio
async def test_sync_preserves_git_node(local_repo):
    """board.git (with sync state) survives the update cycle."""
    board = load_board(str(local_repo))
    _init_sync_state(board, local=True, remote=False)
    board.git.sync.time = 42

    await run_sync_cycle(board)

    assert board.git.sync is not None
    assert board.git.sync.time == 42
    assert board.git.sync.status == "idle"


# --- picks up external changes ---


@pytest.mark.asyncio
async def test_sync_picks_up_external_changes(local_repo):
    """An external commit (CLI adds card) is merged into the live tree."""
    board = load_board(str(local_repo))
    _init_sync_state(board, local=True, remote=False)
    original_card_count = len(board.cards)

    # External process adds a card directly to git
    ext_board = load_board(str(local_repo))
    create_card(ext_board, "External card", "Added externally.")
    save_board(ext_board, message="External add")

    await run_sync_cycle(board)

    assert board.git.sync.status == "idle"
    assert len(board.cards) == original_card_count + 1
