"""Save a ganban board to git without touching the working tree."""

import subprocess
from dataclasses import dataclass
from pathlib import Path

from ganban.loader import BRANCH_NAME
from ganban.models import Board, Column, Ticket
from ganban.parser import serialize_markdown


@dataclass
class MergeRequired:
    """Returned by check_for_merge when the branch has diverged."""

    base: str  # common ancestor commit
    ours: str  # our commit (what board was loaded from)
    theirs: str  # their commit (current branch tip)


def check_for_merge(board: Board, branch: str = BRANCH_NAME) -> MergeRequired | None:
    """Check if saving would require a merge.

    Returns MergeRequired with the 3 commit hashes if branch has diverged,
    or None if a simple save is possible.

    The caller can then:
    1. Load all 3 boards: load_board(repo, commit=base/ours/theirs)
    2. Compare them to find conflicts
    3. Build a resolved board
    4. Save with: save_board(resolved, parents=[ours, theirs])
    """
    repo_path = Path(board.repo_path)
    current_tip = _get_branch_tip(repo_path, branch)

    if current_tip is None:
        return None  # Branch doesn't exist, simple save

    if not board.commit:
        return None  # No base commit, simple save

    if current_tip == board.commit:
        return None  # Branch hasn't moved, simple save

    # Branch has moved - find merge base
    merge_base = _get_merge_base(repo_path, board.commit, current_tip)

    if merge_base is None:
        # No common ancestor - shouldn't happen in normal usage
        return None

    return MergeRequired(
        base=merge_base,
        ours=board.commit,
        theirs=current_tip,
    )


def check_remote_for_merge(board: Board, remote: str = "origin", branch: str = BRANCH_NAME) -> MergeRequired | None:
    """Check if a remote has changes that need merging.

    Call this after fetching to see if the remote tracking branch has diverged
    from the board's current commit.

    Args:
        board: The current board state
        remote: Remote name (e.g., "origin")
        branch: Branch name on the remote

    Returns:
        MergeRequired if remote has diverged, None if up to date.
    """
    repo_path = Path(board.repo_path)

    if not board.commit:
        return None  # No base commit

    # Get remote tracking branch commit
    remote_ref = f"refs/remotes/{remote}/{branch}"
    remote_tip = _get_ref(repo_path, remote_ref)

    if remote_tip is None:
        return None  # Remote tracking branch doesn't exist

    if remote_tip == board.commit:
        return None  # Already up to date

    # Find merge base
    merge_base = _get_merge_base(repo_path, board.commit, remote_tip)

    if merge_base is None:
        return None  # No common ancestor

    if merge_base == remote_tip:
        return None  # Remote is behind us, nothing to merge

    return MergeRequired(
        base=merge_base,
        ours=board.commit,
        theirs=remote_tip,
    )


def _get_ref(repo_path: Path, ref: str) -> str | None:
    """Get the commit hash for any ref, or None if it doesn't exist."""
    result = subprocess.run(
        ["git", "rev-parse", "--verify", ref],
        cwd=repo_path,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8").strip()


def save_board(
    board: Board,
    message: str = "Update board",
    branch: str = BRANCH_NAME,
    parents: list[str] | None = None,
) -> str:
    """Save a board to git and return the new commit hash.

    This creates blobs, trees, and a commit without modifying the working tree.

    Args:
        board: The board state to save
        message: Commit message
        branch: Branch name to update
        parents: Explicit parent commits. If None, uses board.commit.
                 For merge commits, pass [ours_commit, theirs_commit].

    Returns:
        The new commit hash
    """
    repo_path = Path(board.repo_path)

    # Build tree from board state
    tree = _build_board_tree(repo_path, board)

    # Determine parents
    if parents is None:
        if board.commit:
            parents = [board.commit]
        else:
            # Check if branch exists
            current_tip = _get_branch_tip(repo_path, branch)
            parents = [current_tip] if current_tip else []

    # Create commit
    parent_args = []
    for parent in parents:
        if parent:
            parent_args.extend(["-p", parent])

    new_commit = _git(
        repo_path,
        ["commit-tree", tree, *parent_args, "-m", message],
    )

    # Update branch ref
    _git(repo_path, ["update-ref", f"refs/heads/{branch}", new_commit])

    return new_commit


def try_auto_merge(
    board: Board,
    merge_info: MergeRequired,
    message: str = "Merge changes",
    branch: str = BRANCH_NAME,
) -> str | None:
    """Attempt an automatic merge if there are no conflicts.

    Args:
        board: The board with our changes
        merge_info: The MergeRequired from check_for_merge
        message: Commit message for the merge
        branch: Branch to update

    Returns:
        The new merge commit hash if successful, None if there are conflicts.
    """
    repo_path = Path(board.repo_path)

    # Build our tree
    our_tree = _build_board_tree(repo_path, board)

    # Attempt 3-way merge
    merged_tree, has_conflicts = _merge_trees(repo_path, merge_info.base, our_tree, merge_info.theirs)

    if has_conflicts:
        return None

    # Clean merge - create merge commit with two parents using the MERGED tree
    parent_args = ["-p", merge_info.ours, "-p", merge_info.theirs]
    new_commit = _git(
        repo_path,
        ["commit-tree", merged_tree, *parent_args, "-m", message],
    )

    # Update branch ref
    _git(repo_path, ["update-ref", f"refs/heads/{branch}", new_commit])

    return new_commit


def _build_board_tree(repo_path: Path, board: Board) -> str:
    """Build the complete tree for a board and return its hash."""
    # Build ticket blobs and .all tree
    ticket_blobs = _hash_tickets(repo_path, board.tickets)
    all_tree = _mktree(
        repo_path,
        [("100644", "blob", sha, f"{ticket_id}.md") for ticket_id, sha in ticket_blobs.items()],
    )

    # Build column trees
    column_trees = []
    for column in board.columns:
        column_tree = _build_column_tree(repo_path, column)
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

    return _mktree(repo_path, root_entries)


def _build_column_tree(repo_path: Path, column: Column) -> str:
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


def _get_branch_tip(repo_path: Path, branch: str) -> str | None:
    """Get the current commit hash of a branch, or None if it doesn't exist."""
    result = subprocess.run(
        ["git", "rev-parse", "--verify", f"refs/heads/{branch}"],
        cwd=repo_path,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8").strip()


def _get_merge_base(repo_path: Path, commit1: str, commit2: str) -> str | None:
    """Find the merge base of two commits, or None if no common ancestor."""
    result = subprocess.run(
        ["git", "merge-base", commit1, commit2],
        cwd=repo_path,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8").strip()


def _merge_trees(repo_path: Path, base_commit: str, our_tree: str, their_commit: str) -> tuple[str, bool]:
    """Attempt a 3-way merge.

    Args:
        repo_path: Path to the git repository
        base_commit: Common ancestor commit
        our_tree: Our tree hash (from _build_board_tree)
        their_commit: Their commit hash

    Returns:
        Tuple of (merged_tree_hash, has_conflicts)
    """
    # git merge-tree --write-tree needs commits, not raw trees.
    # Create a temporary commit for our tree so we can use it in the merge.
    our_temp_commit = _git(repo_path, ["commit-tree", our_tree, "-p", base_commit, "-m", "temp merge commit"])

    # git merge-tree outputs the merged tree hash
    # Exit code 0 = clean merge, non-zero = conflicts
    result = subprocess.run(
        ["git", "merge-tree", "--write-tree", f"--merge-base={base_commit}", our_temp_commit, their_commit],
        cwd=repo_path,
        capture_output=True,
    )

    # First line of output is the tree hash
    output = result.stdout.decode("utf-8").strip()
    tree_hash = output.split("\n")[0] if output else ""

    has_conflicts = result.returncode != 0

    return tree_hash, has_conflicts


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
