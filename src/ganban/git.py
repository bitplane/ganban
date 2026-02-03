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
