"""Tests for git module."""

import pytest
from git import Repo

from ganban.git import (
    create_orphan_branch,
    fetch,
    get_remotes,
    has_branch,
    init_repo,
    is_git_repo,
    push,
)


@pytest.fixture
def temp_repo(tmp_path):
    """Create a temporary git repository."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    repo = Repo.init(repo_path)
    # Create an initial commit so the repo is valid
    (repo_path / "README.md").write_text("# Test")
    repo.index.add(["README.md"])
    repo.index.commit("Initial commit")
    return repo_path


@pytest.fixture
def temp_repo_with_remote(tmp_path):
    """Create a temp repo with a remote pointing to another temp repo."""
    # Create the "remote" repo (bare)
    remote_path = tmp_path / "remote.git"
    Repo.init(remote_path, bare=True)

    # Create the local repo
    repo_path = tmp_path / "local"
    repo_path.mkdir()
    repo = Repo.init(repo_path)

    # Create an initial commit
    (repo_path / "README.md").write_text("# Test")
    repo.index.add(["README.md"])
    repo.index.commit("Initial commit")

    # Add the remote
    repo.create_remote("origin", str(remote_path))
    repo.create_remote("peer", str(remote_path))

    return repo_path


@pytest.mark.asyncio
async def test_get_remotes_empty(temp_repo):
    remotes = await get_remotes(temp_repo)
    assert remotes == []


@pytest.mark.asyncio
async def test_get_remotes_with_remotes(temp_repo_with_remote):
    remotes = await get_remotes(temp_repo_with_remote)
    assert sorted(remotes) == ["origin", "peer"]


@pytest.mark.asyncio
async def test_fetch(temp_repo_with_remote):
    # Just verify it doesn't raise - the remote is empty but valid
    await fetch(temp_repo_with_remote, "origin")


@pytest.mark.asyncio
async def test_push(temp_repo_with_remote):
    """Push a branch to a remote."""
    repo = Repo(temp_repo_with_remote)

    # Create a branch to push
    repo.git.checkout("-b", "ganban")
    (temp_repo_with_remote / "board.md").write_text("# Board")
    repo.index.add(["board.md"])
    repo.index.commit("Add board")

    # Push the branch
    await push(temp_repo_with_remote, "origin", "ganban")

    # Verify it was pushed by fetching and checking ref exists
    remote_repo = repo.remotes.origin
    remote_repo.fetch()
    assert "origin/ganban" in [ref.name for ref in repo.refs]


@pytest.mark.asyncio
async def test_create_orphan_branch(temp_repo):
    """Create an orphan branch without touching working tree."""
    repo = Repo(temp_repo)

    # Verify ganban branch doesn't exist yet
    assert "ganban" not in [h.name for h in repo.heads]

    # Create the orphan branch
    commit = await create_orphan_branch(temp_repo)

    # Branch should exist now
    assert "ganban" in [h.name for h in repo.heads]
    assert len(commit) == 40

    # Should be an orphan (no parents)
    ganban_commit = repo.commit("ganban")
    assert ganban_commit.parents == ()

    # Working tree should be unchanged (still on master with README)
    assert repo.active_branch.name == "master"
    assert (temp_repo / "README.md").exists()


def test_is_git_repo_true(temp_repo):
    """Returns True for a git repository."""
    assert is_git_repo(temp_repo) is True


def test_is_git_repo_false(tmp_path):
    """Returns False for a non-git directory."""
    assert is_git_repo(tmp_path) is False


def test_init_repo(tmp_path):
    """Initialize a new git repository."""
    new_repo_path = tmp_path / "new_repo"
    new_repo_path.mkdir()

    repo = init_repo(new_repo_path)

    assert repo is not None
    assert is_git_repo(new_repo_path)


def test_has_branch_true(temp_repo):
    """Returns True when branch exists."""
    assert has_branch(temp_repo, "master") is True


def test_has_branch_false(temp_repo):
    """Returns False when branch doesn't exist."""
    assert has_branch(temp_repo, "ganban") is False


@pytest.mark.asyncio
async def test_has_branch_after_create(temp_repo):
    """has_branch returns True after creating orphan branch."""
    assert has_branch(temp_repo, "ganban") is False
    await create_orphan_branch(temp_repo)
    assert has_branch(temp_repo, "ganban") is True
