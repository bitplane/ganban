"""Save a ganban board (Node tree) to git without touching the working tree."""

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ganban.ids import pad_id
from ganban.model.column import slugify
from ganban.constants import BRANCH_NAME
from ganban.model.node import ListNode, Node
from ganban.parser import first_title, serialize_sections


# --- Helpers for converting Node tree back to serializable form ---


def _meta_to_dict(meta) -> dict:
    """Convert a meta value (Node or dict) back to a plain dict, recursively."""
    if isinstance(meta, Node):
        return {k: _meta_to_dict(v) if isinstance(v, Node) else v for k, v in meta.items()}
    if isinstance(meta, dict):
        return meta
    return {}


def _sections_to_text(sections: ListNode, meta) -> str:
    """Serialize a sections ListNode + meta back to markdown text."""
    meta_dict = _meta_to_dict(meta)
    return serialize_sections(sections.items(), meta_dict or None)


# --- Git plumbing ---


def _git(repo_path: Path, args: list[str]) -> str:
    """Run a git command and return stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=repo_path,
        capture_output=True,
        check=True,
    )
    return result.stdout.decode("utf-8").strip()


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


def _get_branch_tip(repo_path: Path, branch: str) -> str | None:
    """Get the current commit hash of a branch, or None if it doesn't exist."""
    return _get_ref(repo_path, f"refs/heads/{branch}")


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


def _commit_timestamp(repo_path: Path, commit: str) -> int:
    """Get the committer timestamp of a commit as epoch seconds."""
    return int(_git(repo_path, ["log", "-1", "--format=%ct", commit]))


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


def _merge_trees(
    repo_path: Path,
    base_commit: str,
    our_tree: str,
    their_commit: str,
) -> tuple[str, list[str]]:
    """Attempt a 3-way merge.

    Returns:
        Tuple of (merged_tree_hash, conflict_paths).
        conflict_paths is empty on a clean merge.
    """
    our_temp_commit = _git(repo_path, ["commit-tree", our_tree, "-p", base_commit, "-m", "temp merge commit"])

    result = subprocess.run(
        ["git", "merge-tree", "--write-tree", f"--merge-base={base_commit}", our_temp_commit, their_commit],
        cwd=repo_path,
        capture_output=True,
    )

    output = result.stdout.decode("utf-8").strip()
    lines = output.split("\n")
    tree_hash = lines[0] if lines else ""
    conflict_paths = re.findall(r"CONFLICT \([^)]+\): .+ (\S+)$", output, re.MULTILINE)

    return tree_hash, conflict_paths


def _resolve_conflicts(repo_path: Path, merged_tree: str, winner_commit: str, conflict_paths: list[str]) -> str:
    """Replace conflicted paths in merged_tree with the winner's versions.

    Uses a temporary index to surgically swap only the conflicted blobs,
    preserving the cleanly-merged content for everything else.
    """
    fd, idx = tempfile.mkstemp(prefix="ganban_idx_")
    os.close(fd)
    try:
        env = {**os.environ, "GIT_INDEX_FILE": idx}
        subprocess.run(["git", "read-tree", merged_tree], cwd=repo_path, env=env, check=True)
        for path in conflict_paths:
            # Get the entry (mode + blob) from the winner's tree
            entry = subprocess.run(
                ["git", "ls-tree", winner_commit, path],
                cwd=repo_path,
                capture_output=True,
            )
            entry_line = entry.stdout.decode("utf-8").strip()
            if entry_line:
                # File exists in winner: replace the blob
                mode, _, blob = entry_line.split(None, 2)
                blob = blob.split("\t")[0]
                subprocess.run(
                    ["git", "update-index", "--cacheinfo", f"{mode},{blob},{path}"],
                    cwd=repo_path,
                    env=env,
                    check=True,
                )
            else:
                # File deleted in winner: remove from index
                subprocess.run(
                    ["git", "update-index", "--force-remove", path],
                    cwd=repo_path,
                    env=env,
                    check=True,
                )
        result = subprocess.run(
            ["git", "write-tree"],
            cwd=repo_path,
            env=env,
            capture_output=True,
            check=True,
        )
        return result.stdout.decode("utf-8").strip()
    finally:
        os.unlink(idx)


# --- Board tree building ---


def _build_board_tree(repo_path: Path, board: Node) -> str:
    """Build the complete git tree for a board and return its hash."""
    # Build card blobs and .all tree
    width = max(max((len(cid) for cid in board.cards.keys()), default=1), 3)
    card_entries = []
    for card_id, card in board.cards.items():
        text = _sections_to_text(card.sections, card.meta)
        blob = _hash_object(repo_path, text)
        card_entries.append(("100644", "blob", blob, f"{pad_id(card_id, width)}.md"))

    all_tree = _mktree(repo_path, card_entries)

    # Build column trees
    column_trees = []
    for col in board.columns:
        col_tree = _build_column_tree(repo_path, col, board, width)
        column_trees.append((col.dir_path, col_tree))

    # Build root tree entries
    root_entries = [("040000", "tree", all_tree, ".all")]

    for dir_path, tree_sha in column_trees:
        root_entries.append(("040000", "tree", tree_sha, dir_path))

    index_blob = _hash_object(repo_path, _sections_to_text(board.sections, board.meta))
    root_entries.append(("100644", "blob", index_blob, "index.md"))

    return _mktree(repo_path, root_entries)


def _build_column_tree(repo_path: Path, col: Node, board: Node, width: int = 3) -> str:
    """Build a git tree for a column directory."""
    entries = []

    index_blob = _hash_object(repo_path, _sections_to_text(col.sections, col.meta))
    entries.append(("100644", "blob", index_blob, "index.md"))

    # Add symlinks for card links
    for i, card_id in enumerate(col.links):
        card = board.cards[card_id]
        title = first_title(card.sections) if card else ""
        slug = slugify(title)
        position = f"{i + 1:02d}"
        target = f"../.all/{pad_id(card_id, width)}.md"
        symlink_blob = _hash_object(repo_path, target)
        filename = f"{position}.{slug}.md"
        entries.append(("120000", "blob", symlink_blob, filename))

    return _mktree(repo_path, entries)


# --- Public API ---


@dataclass
class MergeRequired:
    """Returned by check_for_merge when the branch has diverged."""

    base: str
    ours: str
    theirs: str


def save_board(
    board: Node,
    message: str = "Update board",
    branch: str = BRANCH_NAME,
    parents: list[str] | None = None,
) -> str:
    """Save a board to git and return the new commit hash."""
    repo_path = Path(board.repo_path)

    tree = _build_board_tree(repo_path, board)

    if parents is None:
        if board.commit:
            parents = [board.commit]
        else:
            current_tip = _get_branch_tip(repo_path, branch)
            parents = [current_tip] if current_tip else []

    # Skip commit if tree is unchanged from parent
    if len(parents) == 1 and parents[0]:
        parent_tree = _git(repo_path, ["rev-parse", f"{parents[0]}^{{tree}}"])
        if parent_tree == tree:
            return board.commit

    parent_args = []
    for parent in parents:
        if parent:
            parent_args.extend(["-p", parent])

    new_commit = _git(
        repo_path,
        ["commit-tree", tree, *parent_args, "-m", message],
    )

    _git(repo_path, ["update-ref", f"refs/heads/{branch}", new_commit])

    return new_commit


def _check_divergence(
    repo_path: Path,
    our_commit: str,
    their_commit: str | None,
    skip_if_ancestor: bool = False,
) -> MergeRequired | None:
    """Check if our_commit and their_commit have diverged."""
    if their_commit is None or their_commit == our_commit:
        return None
    merge_base = _get_merge_base(repo_path, our_commit, their_commit)
    if merge_base is None:
        return None
    if skip_if_ancestor and merge_base == their_commit:
        return None
    return MergeRequired(base=merge_base, ours=our_commit, theirs=their_commit)


def check_for_merge(board: Node, branch: str = BRANCH_NAME) -> MergeRequired | None:
    """Check if saving would require a merge."""
    if not board.commit:
        return None
    repo_path = Path(board.repo_path)
    current_tip = _get_branch_tip(repo_path, branch)
    return _check_divergence(repo_path, board.commit, current_tip)


def check_remote_for_merge(board: Node, remote: str = "origin", branch: str = BRANCH_NAME) -> MergeRequired | None:
    """Check if a remote has changes that need merging."""
    if not board.commit:
        return None
    repo_path = Path(board.repo_path)
    remote_tip = _get_ref(repo_path, f"refs/remotes/{remote}/{branch}")
    return _check_divergence(repo_path, board.commit, remote_tip, skip_if_ancestor=True)


def try_auto_merge(
    board: Node,
    merge_info: MergeRequired,
    message: str = "Merge changes",
    branch: str = BRANCH_NAME,
) -> str | None:
    """Attempt an automatic merge, resolving conflicts with most-recent-commit-wins.

    Returns the new merge commit hash. Conflicts are resolved by replacing
    conflicted files with the version from whichever commit is newer.
    Returns None only if merge-tree fails entirely.
    """
    repo_path = Path(board.repo_path)

    our_tree = _build_board_tree(repo_path, board)

    # Fast-forward: our tree matches the merge base, so we're just behind
    base_tree = _git(repo_path, ["rev-parse", f"{merge_info.base}^{{tree}}"])
    if our_tree == base_tree:
        _git(repo_path, ["update-ref", f"refs/heads/{branch}", merge_info.theirs])
        return merge_info.theirs

    merged_tree, conflict_paths = _merge_trees(repo_path, merge_info.base, our_tree, merge_info.theirs)

    if conflict_paths:
        # Most-recent-commit-wins: replace only the conflicted files.
        # Non-conflicting changes from both sides are preserved in merged_tree.
        # TODO: revisit with UI-assisted resolution.
        ours_ts = _commit_timestamp(repo_path, merge_info.ours)
        theirs_ts = _commit_timestamp(repo_path, merge_info.theirs)
        winner = merge_info.theirs if theirs_ts >= ours_ts else merge_info.ours
        merged_tree = _resolve_conflicts(repo_path, merged_tree, winner, conflict_paths)

    parent_args = ["-p", merge_info.ours, "-p", merge_info.theirs]
    new_commit = _git(
        repo_path,
        ["commit-tree", merged_tree, *parent_args, "-m", message],
    )

    _git(repo_path, ["update-ref", f"refs/heads/{branch}", new_commit])

    return new_commit
