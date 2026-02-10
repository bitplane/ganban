"""Git operations for ganban, with sync and async variants."""

import asyncio
from pathlib import Path

from git import InvalidGitRepositoryError, Repo

CONFIG_DEFAULTS = {
    "sync-interval": 30,
    "sync-local": True,
    "sync-remote": True,
}

_GIT_TO_PYTHON = {k: k.replace("-", "_") for k in CONFIG_DEFAULTS}
_PYTHON_TO_GIT = {v: k for k, v in _GIT_TO_PYTHON.items()}


def _parse_config_value(git_key: str, raw: str):
    """Parse a raw git config string into the right Python type."""
    default = CONFIG_DEFAULTS[git_key]
    if isinstance(default, bool):
        return raw.lower() in ("true", "yes", "1")
    if isinstance(default, int):
        return int(raw)
    return raw


def read_ganban_config(repo_path: str | Path) -> dict:
    """Read ganban.* keys from local git config, returned as python-keyed dict."""
    repo = _get_repo(repo_path)
    reader = repo.config_reader("repository")
    result = {}
    for git_key, default in CONFIG_DEFAULTS.items():
        py_key = _GIT_TO_PYTHON[git_key]
        try:
            raw = reader.get_value("ganban", git_key)
            result[py_key] = _parse_config_value(git_key, str(raw))
        except Exception:
            result[py_key] = default
    return result


def write_ganban_config_key(repo_path: str | Path, key: str, value) -> None:
    """Write one ganban.* key to local git config.

    key is the python name (e.g. sync_interval), converted to git name (sync-interval).
    """
    git_key = _PYTHON_TO_GIT[key]
    repo = _get_repo(repo_path)
    writer = repo.config_writer("repository")
    if isinstance(value, bool):
        writer.set_value("ganban", git_key, str(value).lower())
    else:
        writer.set_value("ganban", git_key, str(value))
    writer.release()


def _get_repo(repo_path: str | Path) -> Repo:
    return Repo(repo_path)


def is_git_repo(path: str | Path) -> bool:
    """Check if path is inside a git repository."""
    try:
        Repo(path)
        return True
    except InvalidGitRepositoryError:
        return False


def init_repo(path: str | Path) -> Repo:
    """Initialize a new git repository at path."""
    return Repo.init(path)


# --- Sync functions ---


def get_remotes_sync(repo_path: str | Path) -> list[str]:
    """Get list of remote names for a repository."""
    repo = _get_repo(repo_path)
    return [remote.name for remote in repo.remotes]


def fetch_sync(repo_path: str | Path, remote_name: str) -> None:
    """Fetch from a specific remote."""
    repo = _get_repo(repo_path)
    remote = repo.remote(remote_name)
    remote.fetch()


def push_sync(repo_path: str | Path, remote_name: str, branch: str = "ganban") -> None:
    """Push a branch to a remote."""
    repo = _get_repo(repo_path)
    remote = repo.remote(remote_name)
    remote.push(branch)


def get_upstream(repo_path: str | Path, branch: str = "ganban") -> tuple[str, str] | None:
    """Get the upstream remote and branch for a local branch.

    Returns (remote_name, remote_branch) or None if no tracking branch is set.
    """
    repo = _get_repo(repo_path)
    try:
        head = repo.heads[branch]
    except (IndexError, ValueError):
        return None
    tracking = head.tracking_branch()
    if tracking is None:
        return None
    return tracking.remote_name, tracking.name.split("/", 1)[1]


def remote_has_branch(repo_path: str | Path, remote_name: str, branch: str = "ganban") -> bool:
    """Check if refs/remotes/{remote}/{branch} exists."""
    repo = _get_repo(repo_path)
    ref = f"refs/remotes/{remote_name}/{branch}"
    try:
        repo.git.rev_parse("--verify", ref)
        return True
    except Exception:
        return False


# --- Async wrappers ---


async def has_branch(repo_path: str | Path, branch: str = "ganban") -> bool:
    """Check if a branch exists in the repository."""

    def _has_branch():
        repo = _get_repo(repo_path)
        return branch in [h.name for h in repo.heads]

    return await asyncio.to_thread(_has_branch)


async def get_remotes(repo_path: str | Path) -> list[str]:
    """Get list of remote names for a repository."""
    return await asyncio.to_thread(get_remotes_sync, repo_path)


async def fetch(repo_path: str | Path, remote_name: str) -> None:
    """Fetch from a specific remote."""
    await asyncio.to_thread(fetch_sync, repo_path, remote_name)


async def push(repo_path: str | Path, remote_name: str, branch: str = "ganban") -> None:
    """Push a branch to a remote."""
    await asyncio.to_thread(push_sync, repo_path, remote_name, branch)


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
