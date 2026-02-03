"""Async wrappers around GitPython for non-blocking git operations."""

import asyncio
from pathlib import Path

from git import Repo


def _get_repo(repo_path: str | Path) -> Repo:
    return Repo(repo_path)


async def get_remotes(repo_path: str | Path) -> list[str]:
    """Get list of remote names for a repository."""

    def _get_remotes():
        repo = _get_repo(repo_path)
        return [remote.name for remote in repo.remotes]

    return await asyncio.to_thread(_get_remotes)


async def fetch(repo_path: str | Path, remote_name: str) -> None:
    """Fetch from a specific remote."""

    def _fetch():
        repo = _get_repo(repo_path)
        remote = repo.remote(remote_name)
        remote.fetch()

    await asyncio.to_thread(_fetch)


async def push(repo_path: str | Path, remote_name: str, branch: str = "ganban") -> None:
    """Push a branch to a remote."""

    def _push():
        repo = _get_repo(repo_path)
        remote = repo.remote(remote_name)
        remote.push(branch)

    await asyncio.to_thread(_push)


async def create_orphan_branch(repo_path: str | Path, branch: str = "ganban") -> str:
    """Create an orphan branch with an empty commit.

    Does not touch the working tree. Returns the commit hash.
    """

    def _create():
        repo = _get_repo(repo_path)

        # Create empty tree
        empty_tree = repo.git.hash_object("-t", "tree", "/dev/null")

        # Create commit with no parents
        commit = repo.git.commit_tree(empty_tree, m="Initialize ganban board")

        # Create the branch ref
        repo.git.update_ref(f"refs/heads/{branch}", commit)

        return commit

    return await asyncio.to_thread(_create)
