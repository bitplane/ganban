"""Tests for git module."""

import pytest
from git import Repo

from ganban.git import fetch, get_remotes, push


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
