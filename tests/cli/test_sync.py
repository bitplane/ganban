"""Tests for ganban sync command."""

import json
import signal
import subprocess
import tempfile
import time

import pytest
from git import Repo

from ganban.cli.sync import _do_sync, sync
from ganban.model.card import create_card
from ganban.model.column import create_column
from ganban.model.loader import load_board
from ganban.model.node import ListNode, Node
from ganban.model.writer import save_board


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


@pytest.fixture
def synced_repos(tmp_path):
    """Create a local repo + bare remote, both with ganban branch, origin configured."""
    remote_path = tmp_path / "remote.git"
    Repo.init(remote_path, bare=True)

    local_path = tmp_path / "local"
    local_path.mkdir()
    local_repo = Repo.init(local_path)

    # Initial commit on master so repo is valid
    (local_path / ".gitkeep").write_text("")
    local_repo.index.add([".gitkeep"])
    local_repo.index.commit("Initial commit")

    # Create ganban board
    _make_board_and_save(local_path)

    # Add remote and push
    local_repo.create_remote("origin", str(remote_path))
    local_repo.git.push("origin", "ganban")

    return local_path, remote_path


def _clone_and_push_card(remote_path, card_title="Remote card", card_body="Added remotely.", card_id=None):
    """Clone remote, add a card, push back. Returns the new commit hex."""
    with tempfile.TemporaryDirectory() as other_path:
        other_repo = Repo.clone_from(str(remote_path), other_path)
        other_repo.git.checkout("ganban")

        board = load_board(other_path)
        if card_id:
            # Add card with explicit ID to avoid collisions
            sections = ListNode()
            sections[card_title] = card_body
            board.cards[card_id] = Node(sections=sections, meta={}, file_path=f".all/{card_id}.md")
            col = list(board.columns)[0]
            col.links = list(col.links) + [card_id]
        else:
            create_card(board, card_title, card_body)
        save_board(board, message=f"Add {card_title}")

        other_repo.git.push("origin", "ganban")
        return other_repo.head.commit.hexsha


# --- no remotes ---


def test_sync_no_remotes(tmp_path):
    """Sync with no remotes returns 0, no error."""
    Repo.init(tmp_path)
    (tmp_path / ".gitkeep").write_text("")
    repo = Repo(tmp_path)
    repo.index.add([".gitkeep"])
    repo.index.commit("Initial commit")
    _make_board_and_save(tmp_path)

    exit_code, result = _do_sync(str(tmp_path))

    assert exit_code == 0
    assert result["fetched"] == []
    assert result["merged"] == []
    assert result["pushed"] is None
    assert result["error"] is None


# --- no changes ---


def test_sync_no_changes(synced_repos):
    """Fetch succeeds, nothing to merge, push succeeds."""
    local_path, _ = synced_repos

    exit_code, result = _do_sync(str(local_path))

    assert exit_code == 0
    assert "origin" in result["fetched"]
    assert result["merged"] == []
    assert result["pushed"] == "origin"
    assert result["error"] is None


# --- merge remote changes ---


def test_sync_merge_remote_changes(synced_repos):
    """Other clone pushes a new card, sync merges it."""
    local_path, remote_path = synced_repos

    _clone_and_push_card(remote_path)

    exit_code, result = _do_sync(str(local_path))

    assert exit_code == 0
    assert "origin" in result["merged"]

    board = load_board(str(local_path))
    assert len(board.cards) == 2


# --- merge conflict exits 1 ---


def test_sync_merge_conflict(synced_repos):
    """Both sides edit same card file, sync returns exit code 1."""
    local_path, remote_path = synced_repos

    # Remote edits card 001
    with tempfile.TemporaryDirectory() as other_path:
        other_repo = Repo.clone_from(str(remote_path), other_path)
        other_repo.git.checkout("ganban")

        board = load_board(other_path)
        board.cards["001"].sections["First card"] = "Remote edit."
        save_board(board, message="Remote edit card")
        other_repo.git.push("origin", "ganban")

    # Local edits card 001
    board = load_board(str(local_path))
    board.cards["001"].sections["First card"] = "Local edit."
    save_board(board, message="Local edit card")

    exit_code, result = _do_sync(str(local_path))

    assert exit_code == 1
    assert result["error"] is not None
    assert "conflict" in result["error"]


# --- push local changes ---


def test_sync_push_local_changes(synced_repos):
    """Local ahead, push to remote."""
    local_path, remote_path = synced_repos

    board = load_board(str(local_path))
    create_card(board, "Local card", "Added locally.")
    save_board(board, message="Add local card")

    exit_code, result = _do_sync(str(local_path))

    assert exit_code == 0
    assert result["pushed"] == "origin"

    # Verify remote got the push
    with tempfile.TemporaryDirectory() as check_path:
        check_repo = Repo.clone_from(str(remote_path), check_path)
        check_repo.git.checkout("ganban")
        check_board = load_board(check_path)
        assert len(check_board.cards) == 2


# --- multiple remotes ---


def test_sync_multiple_remotes(tmp_path):
    """Two remotes with different changes, both merged."""
    remote1_path = tmp_path / "remote1.git"
    remote2_path = tmp_path / "remote2.git"
    Repo.init(remote1_path, bare=True)
    Repo.init(remote2_path, bare=True)

    local_path = tmp_path / "local"
    local_path.mkdir()
    local_repo = Repo.init(local_path)
    (local_path / ".gitkeep").write_text("")
    local_repo.index.add([".gitkeep"])
    local_repo.index.commit("Initial commit")

    _make_board_and_save(local_path)

    local_repo.create_remote("origin", str(remote1_path))
    local_repo.create_remote("peer", str(remote2_path))
    local_repo.git.push("origin", "ganban")
    local_repo.git.push("peer", "ganban")

    # Push different cards with explicit non-colliding IDs
    _clone_and_push_card(remote1_path, "Card from remote1", "From remote1.", card_id="r01")
    _clone_and_push_card(remote2_path, "Card from remote2", "From remote2.", card_id="r02")

    exit_code, result = _do_sync(str(local_path))

    assert exit_code == 0
    assert len(result["merged"]) == 2

    board = load_board(str(local_path))
    assert len(board.cards) == 3


# --- remote without ganban branch ---


def test_sync_remote_without_ganban(tmp_path):
    """Remote without ganban branch is skipped gracefully."""
    remote_with = tmp_path / "with.git"
    remote_without = tmp_path / "without.git"
    Repo.init(remote_with, bare=True)
    Repo.init(remote_without, bare=True)

    local_path = tmp_path / "local"
    local_path.mkdir()
    local_repo = Repo.init(local_path)
    (local_path / ".gitkeep").write_text("")
    local_repo.index.add([".gitkeep"])
    local_repo.index.commit("Initial commit")

    _make_board_and_save(local_path)

    local_repo.create_remote("origin", str(remote_with))
    local_repo.create_remote("empty", str(remote_without))
    local_repo.git.push("origin", "ganban")

    _clone_and_push_card(remote_with, "Remote card")

    exit_code, result = _do_sync(str(local_path))

    assert exit_code == 0
    assert "origin" in result["merged"]
    # empty remote was fetched but not merged (no ganban branch)
    assert "empty" not in result["merged"]


# --- daemon signal handling ---


def test_sync_daemon_signal(synced_repos):
    """Daemon starts, runs at least one cycle, stops on SIGTERM."""
    local_path, _ = synced_repos

    proc = subprocess.Popen(
        ["python", "-m", "ganban", "sync", "-d", "--interval", "300", "--repo", str(local_path)],
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )

    # Give it a moment to start and complete one sync cycle
    time.sleep(2)

    proc.send_signal(signal.SIGTERM)
    proc.wait(timeout=5)

    assert proc.returncode == 0


# --- json output ---


def test_sync_json_output(synced_repos):
    """--json produces structured output."""
    local_path, _ = synced_repos

    proc = subprocess.Popen(
        ["python", "-m", "ganban", "sync", "--json", "--repo", str(local_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = proc.communicate(timeout=10)

    assert proc.returncode == 0

    data = json.loads(stdout.decode())
    assert "fetched" in data
    assert "merged" in data
    assert "pushed" in data


# --- sync handler ---


def test_sync_handler_no_changes(synced_repos, capsys):
    """sync() handler prints 'nothing to do' when no changes (besides fetch/push)."""
    local_path, _ = synced_repos

    class Args:
        repo = str(local_path)
        json = False
        daemon = False
        interval = 120

    exit_code = sync(Args())
    assert exit_code == 0
    captured = capsys.readouterr()
    # Should show at least fetched and pushed
    assert "fetched" in captured.out or "nothing to do" in captured.out
