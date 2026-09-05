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
    board.git.config = Node(ganban=Node(sync_local=local, sync_remote=remote, sync_interval=30))


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
        other_board.cards["r01"] = Node(sections=sections, meta={})
        col = list(other_board.columns)[0]
        col.links = tuple(list(col.links) + ["r01"])
        save_board(other_board, message="Add remote card")
        other_repo.git.push("origin", "ganban")

    board = load_board(str(local_path))
    _init_sync_state(board, local=True, remote=True)

    await run_sync_cycle(board)

    assert board.git.sync.status == "idle"
    assert len(board.cards) == 2


# --- conflict ---


@pytest.mark.asyncio
async def test_sync_conflict_resolves(synced_repos):
    """Same file edited both sides → most-recent-commit-wins resolves it."""
    local_path, remote_path = synced_repos

    # Remote edits card 001
    with tempfile.TemporaryDirectory() as other_path:
        other_repo = Repo.clone_from(str(remote_path), other_path)
        other_repo.git.checkout("ganban")
        other_board = load_board(other_path)
        other_board.cards["1"].sections["First card"] = "Remote edit."
        save_board(other_board, message="Remote edit")
        other_repo.git.push("origin", "ganban")

    # Local edits card 001
    board = load_board(str(local_path))
    board.cards["1"].sections["First card"] = "Local edit."
    save_board(board, message="Local edit")

    # Reload so commit is fresh
    board = load_board(str(local_path))
    _init_sync_state(board, local=True, remote=True)

    await run_sync_cycle(board)

    # Conflict resolved, not stuck
    assert board.git.sync.status == "idle"


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


@pytest.mark.asyncio
async def test_sync_preserves_edits_after_save_snapshot(local_repo):
    """A merge reload must not replace edits made after the save snapshot."""
    board = load_board(str(local_repo))
    _init_sync_state(board, local=True, remote=False)

    external = load_board(str(local_repo))
    external.cards["1"].sections["External notes"] = "Keep this too."
    save_board(external, message="External edit")

    def edit_after_snapshot(node, key, old, new):
        if new == "load":
            board.cards["1"].sections["First card"] = "Unsaved live edit."

    unwatch = board.git.sync.watch("status", edit_after_snapshot)
    await run_sync_cycle(board)
    unwatch()

    assert board.cards["1"].sections["First card"] == "Unsaved live edit."
    assert board.git.sync.status == "idle"

    # The next cycle must save the live edit and incorporate the external
    # change, rather than claiming the stale live tree includes the merge.
    await run_sync_cycle(board)
    reloaded = load_board(str(local_repo))
    for result in (board, reloaded):
        assert result.cards["1"].sections["First card"] == "Unsaved live edit."
        assert result.cards["1"].sections["External notes"] == "Keep this too."


@pytest.mark.asyncio
@pytest.mark.parametrize("edit_kind", ["board", "column", "labels", "new_card"])
async def test_sync_preserves_other_live_changes(local_repo, edit_kind):
    """Reload protection covers structure and metadata, not just card text."""
    initial = load_board(str(local_repo))
    initial.cards["1"].meta.labels = ["existing"]
    save_board(initial)
    board = load_board(str(local_repo))
    _init_sync_state(board, local=True, remote=False)

    external = load_board(str(local_repo))
    external.cards["1"].sections["External notes"] = "Keep this too."
    save_board(external)

    def edit_after_snapshot(node, key, old, new):
        if new != "load":
            return
        if edit_kind == "board":
            board.sections.rename_first_key("Renamed board")
        elif edit_kind == "column":
            board.columns["1"].links = ()
        elif edit_kind == "labels":
            # In-place metadata mutations do not emit Node notifications.
            board.cards["1"].meta.labels.append("late")
        else:
            create_card(board, "Late card", "Created after snapshot.")

    def assert_edit(result):
        if edit_kind == "board":
            assert result.sections.keys() == ["Renamed board"]
        elif edit_kind == "column":
            assert result.columns["1"].links == ()
        elif edit_kind == "labels":
            assert result.cards["1"].meta.labels == ["existing", "late"]
        else:
            assert result.cards["2"].sections["Late card"] == "Created after snapshot."

    unwatch = board.git.sync.watch("status", edit_after_snapshot)
    await run_sync_cycle(board)
    unwatch()
    assert_edit(board)

    await run_sync_cycle(board)
    for result in (board, load_board(str(local_repo))):
        assert_edit(result)
        assert result.cards["1"].sections["External notes"] == "Keep this too."


# --- multiple remotes ---


@pytest.mark.asyncio
@pytest.mark.parametrize("late_edit", [False, True])
async def test_sync_two_remotes_preserves_both(tmp_path, late_edit):
    """Merging a second remote must not discard the first remote's changes."""
    remote_a = tmp_path / "a.git"
    remote_b = tmp_path / "b.git"
    Repo.init(remote_a, bare=True)
    Repo.init(remote_b, bare=True)

    local_path = tmp_path / "local"
    local_path.mkdir()
    local_repo = Repo.init(local_path)
    (local_path / ".gitkeep").write_text("")
    local_repo.index.add([".gitkeep"])
    local_repo.index.commit("Initial commit")
    _make_board_and_save(local_path)

    local_repo.create_remote("a", str(remote_a))
    local_repo.create_remote("b", str(remote_b))
    local_repo.git.push("a", "ganban")
    local_repo.git.push("b", "ganban")

    # Each remote gains a distinct card via its own clone
    for name, remote_path, card_id in (("a", remote_a, "a01"), ("b", remote_b, "b01")):
        with tempfile.TemporaryDirectory() as other_path:
            other_repo = Repo.clone_from(str(remote_path), other_path)
            other_repo.git.checkout("ganban")
            other_board = load_board(other_path)
            sections = ListNode()
            sections[f"Card {name}"] = "Added remotely."
            other_board.cards[card_id] = Node(sections=sections, meta={})
            col = list(other_board.columns)[0]
            col.links = tuple(list(col.links) + [card_id])
            save_board(other_board, message=f"Add card {name}")
            other_repo.git.push("origin", "ganban")

    board = load_board(str(local_path))
    _init_sync_state(board, local=True, remote=True)

    def edit_after_snapshot(node, key, old, new):
        if late_edit and new == "load":
            board.cards["1"].sections["First card"] = "Late edit with two remotes."

    unwatch = board.git.sync.watch("status", edit_after_snapshot)
    await run_sync_cycle(board)
    unwatch()

    if late_edit:
        assert board.cards["1"].sections["First card"] == "Late edit with two remotes."
        await run_sync_cycle(board)

    assert board.git.sync.status == "idle"
    # Both remotes' cards survived the double merge
    reloaded = load_board(str(local_path))
    assert len(reloaded.cards) == 3
    assert len(board.cards) == 3
    if late_edit:
        assert reloaded.cards["1"].sections["First card"] == "Late edit with two remotes."
