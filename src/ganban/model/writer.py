"""Save a ganban board (Node tree) to git without touching the working tree."""

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ganban.ids import max_id, next_id
from ganban.model.node import BRANCH_NAME, ListNode, Node
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


# --- Git plumbing (copied verbatim from writer.py) ---


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
    result = subprocess.run(
        ["git", "rev-parse", "--verify", f"refs/heads/{branch}"],
        cwd=repo_path,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8").strip()


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

    Returns:
        Tuple of (merged_tree_hash, has_conflicts)
    """
    our_temp_commit = _git(repo_path, ["commit-tree", our_tree, "-p", base_commit, "-m", "temp merge commit"])

    result = subprocess.run(
        ["git", "merge-tree", "--write-tree", f"--merge-base={base_commit}", our_temp_commit, their_commit],
        cwd=repo_path,
        capture_output=True,
    )

    output = result.stdout.decode("utf-8").strip()
    tree_hash = output.split("\n")[0] if output else ""
    has_conflicts = result.returncode != 0

    return tree_hash, has_conflicts


# --- Board tree building ---


def _build_board_tree(repo_path: Path, board: Node) -> str:
    """Build the complete git tree for a board and return its hash."""
    # Build card blobs and .all tree
    card_entries = []
    for card_id, card in board.cards.items():
        text = _sections_to_text(card.sections, card.meta)
        blob = _hash_object(repo_path, text)
        card_entries.append(("100644", "blob", blob, f"{card_id}.md"))

    all_tree = _mktree(repo_path, card_entries)

    # Build column trees
    column_trees = []
    for col in board.columns:
        col_tree = _build_column_tree(repo_path, col, board)
        column_trees.append((col.dir_path, col_tree))

    # Build root tree entries
    root_entries = [("040000", "tree", all_tree, ".all")]

    for dir_path, tree_sha in column_trees:
        root_entries.append(("040000", "tree", tree_sha, dir_path))

    index_blob = _hash_object(repo_path, _sections_to_text(board.sections, board.meta))
    root_entries.append(("100644", "blob", index_blob, "index.md"))

    return _mktree(repo_path, root_entries)


def _build_column_tree(repo_path: Path, col: Node, board: Node) -> str:
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
        target = f"../.all/{card_id}.md"
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


def check_for_merge(board: Node, branch: str = BRANCH_NAME) -> MergeRequired | None:
    """Check if saving would require a merge."""
    repo_path = Path(board.repo_path)
    current_tip = _get_branch_tip(repo_path, branch)

    if current_tip is None:
        return None

    if not board.commit:
        return None

    if current_tip == board.commit:
        return None

    merge_base = _get_merge_base(repo_path, board.commit, current_tip)

    if merge_base is None:
        return None

    return MergeRequired(
        base=merge_base,
        ours=board.commit,
        theirs=current_tip,
    )


def check_remote_for_merge(board: Node, remote: str = "origin", branch: str = BRANCH_NAME) -> MergeRequired | None:
    """Check if a remote has changes that need merging."""
    repo_path = Path(board.repo_path)

    if not board.commit:
        return None

    remote_ref = f"refs/remotes/{remote}/{branch}"
    remote_tip = _get_ref(repo_path, remote_ref)

    if remote_tip is None:
        return None

    if remote_tip == board.commit:
        return None

    merge_base = _get_merge_base(repo_path, board.commit, remote_tip)

    if merge_base is None:
        return None

    if merge_base == remote_tip:
        return None

    return MergeRequired(
        base=merge_base,
        ours=board.commit,
        theirs=remote_tip,
    )


def try_auto_merge(
    board: Node,
    merge_info: MergeRequired,
    message: str = "Merge changes",
    branch: str = BRANCH_NAME,
) -> str | None:
    """Attempt an automatic merge if there are no conflicts.

    Returns the new merge commit hash if successful, None if there are conflicts.
    """
    repo_path = Path(board.repo_path)

    our_tree = _build_board_tree(repo_path, board)

    merged_tree, has_conflicts = _merge_trees(repo_path, merge_info.base, our_tree, merge_info.theirs)

    if has_conflicts:
        return None

    parent_args = ["-p", merge_info.ours, "-p", merge_info.theirs]
    new_commit = _git(
        repo_path,
        ["commit-tree", merged_tree, *parent_args, "-m", message],
    )

    _git(repo_path, ["update-ref", f"refs/heads/{branch}", new_commit])

    return new_commit


# --- Board manipulation helpers ---


def create_card(
    board: Node,
    title: str,
    body: str = "",
    column: Node | None = None,
    position: int | None = None,
) -> tuple[str, Node]:
    """Create a new card and add it to the board.

    Returns (card_id, card_node).
    """
    card_id = next_id(max_id(board.cards.keys()))

    sections = ListNode()
    sections[title] = body

    card = Node(
        sections=sections,
        meta={},
        file_path=f".all/{card_id}.md",
    )
    board.cards[card_id] = card

    # Add to column
    target_column = column
    if target_column is None:
        for col in board.columns:
            target_column = col
            break

    if target_column is not None:
        links = list(target_column.links)
        if position is not None:
            links.insert(position, card_id)
        else:
            links.append(card_id)
        target_column.links = links

    return card_id, card


def create_column(
    board: Node,
    name: str,
    order: str | None = None,
    hidden: bool = False,
) -> Node:
    """Create a new column and add it to the board.

    Returns the created column Node.
    """
    if order is None:
        existing_orders = board.columns.keys()
        order = next_id(max_id(existing_orders)) if existing_orders else "1"

    sections = ListNode()
    sections[name] = ""
    col = Node(
        order=order,
        dir_path=build_column_path(order, name, hidden),
        hidden=hidden,
        sections=sections,
        meta={},
        links=[],
    )
    board.columns[order] = col

    return col


def slugify(text: str) -> str:
    """Convert text to a URL-friendly slug."""
    slug = text.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "untitled"


def build_column_path(order: str, name: str, hidden: bool = False) -> str:
    """Build column directory path from components."""
    prefix = "." if hidden else ""
    return f"{prefix}{order}.{slugify(name)}"
