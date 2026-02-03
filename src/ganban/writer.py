"""Save a ganban board to git without touching the working tree."""

import subprocess
from pathlib import Path

from ganban.loader import BRANCH_NAME
from ganban.models import Board, Column, Ticket
from ganban.parser import serialize_markdown


def save_board(board: Board, message: str = "Update board", branch: str = BRANCH_NAME) -> str:
    """Save a board to git and return the new commit hash.

    This creates blobs, trees, and a commit without modifying the working tree.
    The board's commit field is used as the parent commit.
    """
    repo_path = Path(board.repo_path)

    # Build ticket blobs and .all tree
    ticket_blobs = _hash_tickets(repo_path, board.tickets)
    all_tree = _mktree(
        repo_path, [("100644", "blob", sha, f"{ticket_id}.md") for ticket_id, sha in ticket_blobs.items()]
    )

    # Build column trees
    column_trees = []
    for column in board.columns:
        column_tree = _build_column_tree(repo_path, column, board.tickets)
        column_trees.append((column.path, column_tree))

    # Build root tree entries
    root_entries = [
        ("040000", "tree", all_tree, ".all"),
    ]

    for path, tree_sha in column_trees:
        root_entries.append(("040000", "tree", tree_sha, path))

    if board.content.title or board.content.body or board.content.sections:
        index_blob = _hash_object(repo_path, serialize_markdown(board.content))
        root_entries.append(("100644", "blob", index_blob, "index.md"))

    root_tree = _mktree(repo_path, root_entries)

    # Create commit
    parent_args = ["-p", board.commit] if board.commit else []
    new_commit = _git(
        repo_path,
        ["commit-tree", root_tree, *parent_args, "-m", message],
    )

    # Update branch ref
    _git(repo_path, ["update-ref", f"refs/heads/{branch}", new_commit])

    return new_commit


def _build_column_tree(repo_path: Path, column: Column, tickets: dict[str, Ticket]) -> str:
    """Build a tree for a column directory."""
    entries = []

    # Add index.md if column has content
    if column.content.title or column.content.body or column.content.sections:
        index_blob = _hash_object(repo_path, serialize_markdown(column.content))
        entries.append(("100644", "blob", index_blob, "index.md"))

    # Add symlinks for ticket links
    for link in column.links:
        target = f"../.all/{link.ticket_id}.md"
        symlink_blob = _hash_object(repo_path, target)
        filename = f"{link.position}.{link.slug}.md"
        entries.append(("120000", "blob", symlink_blob, filename))

    return _mktree(repo_path, entries)


def _hash_tickets(repo_path: Path, tickets: dict[str, Ticket]) -> dict[str, str]:
    """Hash all ticket markdown files and return {ticket_id: blob_sha}."""
    return {
        ticket_id: _hash_object(repo_path, serialize_markdown(ticket.content)) for ticket_id, ticket in tickets.items()
    }


def _hash_object(repo_path: Path, content: str) -> str:
    """Write content to git object store and return the blob hash."""
    result = subprocess.run(
        ["git", "hash-object", "-w", "--stdin"],
        cwd=repo_path,
        input=content.encode("utf-8"),
        capture_output=True,
        check=True,
    )
    return result.stdout.decode("utf-8").strip()


def _mktree(repo_path: Path, entries: list[tuple[str, str, str, str]]) -> str:
    """Create a tree object from entries and return its hash.

    Each entry is (mode, type, sha, name).
    """
    lines = [f"{mode} {typ} {sha}\t{name}" for mode, typ, sha, name in entries]
    content = "\n".join(lines) + "\n" if lines else ""

    result = subprocess.run(
        ["git", "mktree"],
        cwd=repo_path,
        input=content.encode("utf-8"),
        capture_output=True,
        check=True,
    )
    return result.stdout.decode("utf-8").strip()


def _git(repo_path: Path, args: list[str]) -> str:
    """Run a git command and return stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=repo_path,
        capture_output=True,
        check=True,
    )
    return result.stdout.decode("utf-8").strip()
