"""Save a ganban board (Node tree) to git without touching the working tree."""

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from git import Repo
from gitdb.base import IStream

from ganban.ids import max_id, next_id, normalize_id, pad_id
from ganban.model.column import slugify
from ganban.constants import BRANCH_NAME
from ganban.model.node import ListNode, Node
from ganban.parser import first_title, parse_sections, serialize_sections


# --- Helpers for converting Node tree back to serializable form ---


def meta_to_dict(meta) -> dict:
    """Convert a meta value (Node or dict) back to a plain dict, recursively."""
    if isinstance(meta, Node):
        return {k: meta_to_dict(v) if isinstance(v, Node) else v for k, v in meta.items()}
    if isinstance(meta, dict):
        return meta
    return {}


def sections_to_text(sections: ListNode, meta) -> str:
    """Serialize a sections ListNode + meta back to markdown text."""
    meta_dict = meta_to_dict(meta)
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


def _write_blob(repo: Repo, content: str) -> str:
    """Write content to the git object store in-process and return the blob hash.

    Uses gitdb directly instead of spawning `git hash-object` — saves fan
    out to one blob per card/symlink/index, so per-blob subprocesses
    dominate save time on real boards.
    """
    data = content.encode("utf-8")
    return repo.odb.store(IStream("blob", len(data), BytesIO(data))).hexsha.decode("ascii")


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


def _update_ref_cas(repo_path: Path, branch: str, new_commit: str, expected_old: str | None) -> bool:
    """Atomically move a branch to new_commit only if it is still at expected_old.

    expected_old of None means the branch must not exist yet.
    Returns False if the branch moved concurrently.
    """
    result = subprocess.run(
        ["git", "update-ref", f"refs/heads/{branch}", new_commit, expected_old or ""],
        cwd=repo_path,
        capture_output=True,
    )
    return result.returncode == 0


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
        conflict_paths is empty on a clean merge; merged_tree_hash is ""
        if merge-tree failed entirely (exit status above 1).
    """
    our_temp_commit = _git(repo_path, ["commit-tree", our_tree, "-p", base_commit, "-m", "temp merge commit"])

    result = subprocess.run(
        ["git", "merge-tree", "--write-tree", f"--merge-base={base_commit}", our_temp_commit, their_commit],
        cwd=repo_path,
        capture_output=True,
    )

    # merge-tree exits 0 for clean, 1 for conflicts, higher on hard failure
    # (missing objects, unsupported git version) where stdout is unusable
    if result.returncode not in (0, 1):
        return "", []

    output = result.stdout.decode("utf-8")
    lines = output.split("\n")
    tree_hash = lines[0].strip() if lines else ""

    # Conflicted file info lines ("<mode> <oid> <stage>\t<path>") follow the
    # tree line up to a blank line. The informational CONFLICT messages after
    # it are prose — unparseable for paths with spaces or modify/delete.
    conflict_paths: list[str] = []
    for line in lines[1:]:
        if not line.strip():
            break
        _, _, path = line.partition("\t")
        if path and path not in conflict_paths:
            conflict_paths.append(path)

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


# --- Card id collision resolution ---


@dataclass
class MergeRequired:
    """Returned by check_for_merge when the branch has diverged."""

    base: str
    ours: str
    theirs: str


_CARD_PATH_RE = re.compile(r"^\.all/([^/]+)\.md$")
_LINK_TARGET_RE = re.compile(r"^\.\./\.all/([^/]+)\.md$")
_CARD_REF_RE = re.compile(r"#(\d+)\b")


@dataclass
class IdCollision:
    """An .all/ card file added independently on both sides of a merge."""

    path: str
    card_id: str
    ours_blob: str
    theirs_blob: str


def _tree_paths(repo_path: Path, treeish: str) -> dict[str, tuple[str, str]]:
    """Map path -> (mode, blob_sha) for every blob in a tree, recursively."""
    output = _git(repo_path, ["ls-tree", "-r", treeish])
    entries: dict[str, tuple[str, str]] = {}
    for line in output.split("\n"):
        if not line:
            continue
        meta, path = line.split("\t", 1)
        mode, _typ, sha = meta.split()
        entries[path] = (mode, sha)
    return entries


def _read_blob(repo: Repo, sha: str) -> str:
    """Read a blob's content from the object store in-process."""
    return repo.odb.stream(bytes.fromhex(sha)).read().decode("utf-8")


def _first_added(repo_path: Path, commit: str, path: str) -> tuple[int, str] | None:
    """(committer_ts, sha) of the commit that first added path on commit's history."""
    result = subprocess.run(
        ["git", "log", "--diff-filter=A", "--reverse", "--format=%ct %H", commit, "--", path],
        cwd=repo_path,
        capture_output=True,
    )
    first = result.stdout.decode("utf-8").strip().split("\n")[0]
    if result.returncode != 0 or not first:
        return None
    ts, sha = first.split()
    return int(ts), sha


def _find_id_collisions(repo_path: Path, merge_info: MergeRequired, conflict_paths: list[str]) -> list[IdCollision]:
    """Pick out add/add conflicts on .all/ card files: two different cards
    independently created with the same id, not two edits of one card."""
    collisions = []
    base_paths = _tree_paths(repo_path, merge_info.base)
    ours_paths = _tree_paths(repo_path, merge_info.ours)
    theirs_paths = _tree_paths(repo_path, merge_info.theirs)
    for path in conflict_paths:
        match = _CARD_PATH_RE.match(path)
        if not match or path in base_paths:
            continue
        ours = ours_paths.get(path)
        theirs = theirs_paths.get(path)
        if ours and theirs and ours[1] != theirs[1]:
            collisions.append(IdCollision(path, normalize_id(match.group(1)), ours[1], theirs[1]))
    return collisions


def _remap_card_ids(text: str, mapping: dict[str, str]) -> str:
    """Rewrite deps entries and #id reference tokens per mapping.

    Bare numbers are prose and are never touched; #id tokens are real
    references (the UI renders them as links). Returns the original text
    unchanged when nothing matches, to avoid formatting churn.
    """
    sections, meta = parse_sections(text)

    changed = False
    deps = meta.get("deps") if isinstance(meta, dict) else None
    if isinstance(deps, list):
        new_deps = [mapping.get(normalize_id(str(dep)), dep) for dep in deps]
        if new_deps != deps:
            meta["deps"] = new_deps
            changed = True

    def replace(match: re.Match) -> str:
        return "#" + mapping.get(normalize_id(match.group(1)), match.group(1))

    new_sections = []
    for title, body in sections:
        new_title = _CARD_REF_RE.sub(replace, title)
        new_body = _CARD_REF_RE.sub(replace, body)
        if new_title != title or new_body != body:
            changed = True
        new_sections.append((new_title, new_body))

    if not changed:
        return text
    return serialize_sections(new_sections, meta or None)


def _resolve_id_collisions(
    repo_path: Path,
    merge_info: MergeRequired,
    merged_tree: str,
    collisions: list[IdCollision],
) -> str:
    """Renumber colliding new cards so both survive the merge.

    The card that entered history first keeps its id (first-added committer
    timestamp, tiebreak on commit sha — derived from shared history, so
    every replica converges on the same outcome). The newer card moves to
    the next free id; its side's symlinks, deps entries and #id reference
    tokens are rewritten, attributed by comparing blobs against the base.
    """
    repo = Repo(repo_path)
    base_paths = _tree_paths(repo_path, merge_info.base)
    ours_paths = _tree_paths(repo_path, merge_info.ours)
    theirs_paths = _tree_paths(repo_path, merge_info.theirs)
    merged_paths = _tree_paths(repo_path, merged_tree)

    card_stems = [_CARD_PATH_RE.match(p).group(1) for p in merged_paths if _CARD_PATH_RE.match(p)]
    used_ids = {normalize_id(stem) for stem in card_stems}
    width = max((len(stem) for stem in card_stems), default=3)

    # updates: path -> (mode, blob_sha); mapping per side: old id -> new id
    updates: dict[str, tuple[str, str]] = {}
    side_mapping: dict[str, dict[str, str]] = {"ours": {}, "theirs": {}}
    winners: dict[str, str] = {}  # collision path -> winning side
    relocated: list[tuple[str, str, str]] = []  # (new path, blob, side)

    for collision in collisions:
        ours_first = _first_added(repo_path, merge_info.ours, collision.path)
        theirs_first = _first_added(repo_path, merge_info.theirs, collision.path)
        if ours_first and theirs_first:
            ours_keeps = ours_first <= theirs_first
        else:
            ours_keeps = collision.ours_blob < collision.theirs_blob

        winner_blob = collision.ours_blob if ours_keeps else collision.theirs_blob
        loser_blob = collision.theirs_blob if ours_keeps else collision.ours_blob
        loser_side = "theirs" if ours_keeps else "ours"

        new_id = next_id(max_id(list(used_ids)))
        used_ids.add(new_id)
        side_mapping[loser_side][collision.card_id] = new_id

        new_path = f".all/{pad_id(new_id, width)}.md"
        updates[collision.path] = ("100644", winner_blob)
        updates[new_path] = ("100644", loser_blob)
        winners[collision.path] = "ours" if ours_keeps else "theirs"
        relocated.append((new_path, loser_blob, loser_side))

    def side_of(path: str, sha: str) -> str | None:
        """Which side authored this blob, or None if it predates the merge."""
        base = base_paths.get(path)
        if base and base[1] == sha:
            return None
        if ours_paths.get(path, (None, None))[1] == sha:
            return "ours"
        if theirs_paths.get(path, (None, None))[1] == sha:
            return "theirs"
        return None

    # Rewrite pass: every merged blob plus the relocated loser cards, each
    # attributed to the side that authored it so only that side's ids remap.
    # Collision paths use the winner's blob, not merge-tree's marker blob.
    candidates = [
        (path, mode, sha, side_of(path, sha)) for path, (mode, sha) in merged_paths.items() if path not in winners
    ]
    for path, side in winners.items():
        candidates.append((path, "100644", updates[path][1], side))
    for path, sha, side in relocated:
        candidates.append((path, "100644", sha, side))

    for path, mode, sha, side in candidates:
        if side is None or not side_mapping[side]:
            continue
        mapping = side_mapping[side]
        content = _read_blob(repo, sha)
        if mode == "120000":
            match = _LINK_TARGET_RE.match(content)
            if match and normalize_id(match.group(1)) in mapping:
                new_target = f"../.all/{pad_id(mapping[normalize_id(match.group(1))], width)}.md"
                updates[path] = (mode, _write_blob(repo, new_target))
        elif _CARD_PATH_RE.match(path):
            new_content = _remap_card_ids(content, mapping)
            if new_content != content:
                updates[path] = (mode, _write_blob(repo, new_content))

    if not updates:
        return merged_tree

    fd, idx = tempfile.mkstemp(prefix="ganban_idx_")
    os.close(fd)
    try:
        env = {**os.environ, "GIT_INDEX_FILE": idx}
        subprocess.run(["git", "read-tree", merged_tree], cwd=repo_path, env=env, check=True)
        for path, (mode, sha) in updates.items():
            subprocess.run(
                ["git", "update-index", "--add", "--cacheinfo", f"{mode},{sha},{path}"],
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
    repo = Repo(repo_path)

    # Build card blobs and .all tree
    width = max(max((len(cid) for cid in board.cards.keys()), default=1), 3)
    card_entries = []
    for card_id, card in board.cards.items():
        text = sections_to_text(card.sections, card.meta)
        blob = _write_blob(repo, text)
        card_entries.append(("100644", "blob", blob, f"{pad_id(card_id, width)}.md"))

    all_tree = _mktree(repo_path, card_entries)

    # Build column trees
    column_trees = []
    for col in board.columns:
        col_tree = _build_column_tree(repo_path, repo, col, board, width)
        column_trees.append((col.dir_path, col_tree))

    # Build root tree entries
    root_entries = [("040000", "tree", all_tree, ".all")]

    for dir_path, tree_sha in column_trees:
        root_entries.append(("040000", "tree", tree_sha, dir_path))

    index_blob = _write_blob(repo, sections_to_text(board.sections, board.meta))
    root_entries.append(("100644", "blob", index_blob, "index.md"))

    return _mktree(repo_path, root_entries)


def _build_column_tree(repo_path: Path, repo: Repo, col: Node, board: Node, width: int = 3) -> str:
    """Build a git tree for a column directory."""
    entries = []

    index_blob = _write_blob(repo, sections_to_text(col.sections, col.meta))
    entries.append(("100644", "blob", index_blob, "index.md"))

    # Add symlinks for card links
    for i, card_id in enumerate(col.links):
        card = board.cards[card_id]
        title = first_title(card.sections) if card else ""
        slug = slugify(title)
        position = f"{i + 1:02d}"
        target = f"../.all/{pad_id(card_id, width)}.md"
        symlink_blob = _write_blob(repo, target)
        filename = f"{position}.{slug}.md"
        entries.append(("120000", "blob", symlink_blob, filename))

    return _mktree(repo_path, entries)


# --- Public API ---


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

    # The ref may only advance from a commit this save builds on. A tip
    # moved by another process is left in place — the commit still exists
    # and the caller must merge (see save_and_merge) rather than orphan it.
    real_parents = [p for p in parents if p]
    for _ in range(3):
        tip = _get_branch_tip(repo_path, branch)
        if tip == new_commit:
            break
        if tip is not None and tip not in real_parents:
            break
        if _update_ref_cas(repo_path, branch, new_commit, tip):
            break

    return new_commit


def save_and_merge(
    board: Node,
    message: str = "Update board",
    branch: str = BRANCH_NAME,
    max_attempts: int = 5,
) -> tuple[str, bool]:
    """Save the board, merging any concurrent movement of the branch tip.

    Returns (commit, merged). merged is True when a concurrent commit was
    merged in — long-lived callers should reload the board from git, since
    the in-memory tree does not contain the merged-in changes.

    Raises RuntimeError if the branch diverged and auto-merge kept failing;
    the local changes are preserved in the returned commit's history.
    """
    commit = save_board(board, message, branch)
    board.commit = commit
    merged = False
    for _ in range(max_attempts):
        merge_info = check_for_merge(board, branch)
        if merge_info is None:
            return commit, merged
        new_commit = try_auto_merge(board, merge_info, branch=branch)
        if new_commit is not None:
            commit = new_commit
            board.commit = new_commit
            merged = True
    raise RuntimeError(f"branch {branch} diverged and auto-merge failed; local changes saved as {commit}")


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
    Returns None if merge-tree fails entirely, or if the branch moved
    concurrently (merge_info is stale — re-check and retry).
    """
    repo_path = Path(board.repo_path)

    # The ref may only move from a commit that ends up an ancestor of the
    # merge result; any other tip means merge_info is stale.
    tip = _get_branch_tip(repo_path, branch)
    if tip is not None and tip not in (merge_info.ours, merge_info.theirs):
        return None

    our_tree = _build_board_tree(repo_path, board)

    # Fast-forward: our tree matches the merge base, so we're just behind
    base_tree = _git(repo_path, ["rev-parse", f"{merge_info.base}^{{tree}}"])
    if our_tree == base_tree:
        if tip == merge_info.theirs:
            return merge_info.theirs
        if not _update_ref_cas(repo_path, branch, merge_info.theirs, tip):
            return None
        return merge_info.theirs

    merged_tree, conflict_paths = _merge_trees(repo_path, merge_info.base, our_tree, merge_info.theirs)
    if not merged_tree:
        return None

    if conflict_paths:
        # Two different cards created with the same id show up as add/add
        # conflicts on .all/ files; resolve those by renumbering so both
        # cards survive, instead of letting one clobber the other.
        collisions = _find_id_collisions(repo_path, merge_info, conflict_paths)
        collision_paths = {c.path for c in collisions}
        edit_conflicts = [p for p in conflict_paths if p not in collision_paths]

        if edit_conflicts:
            # Most-recent-commit-wins: replace only the conflicted files.
            # Non-conflicting changes from both sides are preserved in merged_tree.
            # TODO: revisit with UI-assisted resolution.
            ours_ts = _commit_timestamp(repo_path, merge_info.ours)
            theirs_ts = _commit_timestamp(repo_path, merge_info.theirs)
            winner = merge_info.theirs if theirs_ts >= ours_ts else merge_info.ours
            merged_tree = _resolve_conflicts(repo_path, merged_tree, winner, edit_conflicts)

        if collisions:
            merged_tree = _resolve_id_collisions(repo_path, merge_info, merged_tree, collisions)

    parent_args = ["-p", merge_info.ours, "-p", merge_info.theirs]
    new_commit = _git(
        repo_path,
        ["commit-tree", merged_tree, *parent_args, "-m", message],
    )

    if not _update_ref_cas(repo_path, branch, new_commit, tip):
        return None

    return new_commit
