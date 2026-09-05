"""Save a ganban board (Node tree) to git without touching the working tree."""

import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from io import BytesIO
from pathlib import Path

from git import Actor, Commit, Repo
from git.db import GitDB
from git.objects.fun import tree_to_stream
from git.objects.util import parse_date
from git.refs import SymbolicReference
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


def _write_blob(repo: Repo, content: str) -> str:
    """Write content to the git object store in-process and return the blob hash.

    Uses gitdb directly instead of spawning `git hash-object` — saves fan
    out to one blob per card/symlink/index, so per-blob subprocesses
    dominate save time on real boards.
    """
    data = content.encode("utf-8")
    return repo.odb.store(IStream("blob", len(data), BytesIO(data))).hexsha.decode("ascii")


def _mktree(repo: Repo, entries: list[tuple[str, str, str, str]]) -> str:
    """Create a tree object from entries and return its hash.

    Each entry is (mode, type, sha, name).
    """
    for _, _, _, name in entries:
        if not name or "/" in name or "\0" in name:
            raise ValueError(f"Invalid tree entry name: {name!r}")
    # Git sorts raw filename bytes, treating directories as ending in '/'.
    entries = sorted(entries, key=lambda e: (e[3] + ("/" if e[1] == "tree" else "")).encode("utf-8"))
    stream = BytesIO()
    tree_to_stream([(bytes.fromhex(sha), int(mode, 8), name) for mode, _, sha, name in entries], stream.write)
    size = stream.tell()
    stream.seek(0)
    return repo.odb.store(IStream("tree", size, stream)).hexsha.decode("ascii")


def _commit_date(env_name: str) -> str | datetime | None:
    """Normalize Git dates before passing them to GitPython.

    GitPython's string parser records ISO/RFC offsets without applying them
    to the timestamp. Aware datetimes preserve both the instant and offset.
    """
    value = os.environ.get(env_name)
    if not value or re.fullmatch(r"@?\d+ [+-]\d{4}", value):
        return value or None
    try:
        date = datetime.fromisoformat(value)
    except ValueError:
        try:
            date = parsedate_to_datetime(value)
        except ValueError:
            # Git also accepts YYYY.MM.DD, MM/DD/YYYY, and DD.MM.YYYY.
            timestamp, offset = parse_date(value)
            date = datetime.fromtimestamp(timestamp, timezone.utc).replace(tzinfo=None)
            if re.search(r"[+-]\d{4}$", value):
                date = date.replace(tzinfo=timezone(timedelta(seconds=-offset)))
    return date.astimezone() if date.tzinfo is None else date


def _write_commit(repo: Repo, tree: str, parents: list[str], message: str) -> str:
    """Create a commit object without updating any refs or the worktree."""
    # GitPython's config reader ignores Git's config environment overrides
    # and does not fully handle linked-worktree configuration. Let Git
    # resolve identity/encoding in those cases instead of writing a commit
    # under the wrong identity. Trees and object reads remain in-process.
    config_overrides = (
        "GIT_CONFIG",
        "GIT_CONFIG_GLOBAL",
        "GIT_CONFIG_SYSTEM",
        "GIT_CONFIG_NOSYSTEM",
        "GIT_CONFIG_COUNT",
        "GIT_CONFIG_PARAMETERS",
    )
    if repo.common_dir != repo.git_dir or any(key in os.environ for key in config_overrides):
        parent_args = [arg for parent in parents if parent for arg in ("-p", parent)]
        return subprocess.run(
            ["git", "commit-tree", tree, *parent_args, "-m", message],
            cwd=repo.working_dir,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    # Match commit-tree -m's terminating newline; an empty message stays empty.
    if message and not message.endswith("\n"):
        message += "\n"
    with repo.config_reader() as config:
        author = Actor.author(config)
        committer = Actor.committer(config)
        config_only = config.get_value("user", "useConfigOnly", False)
        # GitPython reads user.* but not Git's role-specific overrides.
        for role, actor in (("author", author), ("committer", committer)):
            for field in ("name", "email"):
                explicit_env = f"GIT_{role.upper()}_{field.upper()}" in os.environ
                if config_only and not (
                    explicit_env or config.has_option(role, field) or config.has_option("user", field)
                ):
                    raise ValueError(f"{role}.{field} must be configured when user.useConfigOnly is enabled")
                if not explicit_env and config.has_option(role, field):
                    setattr(actor, field, config.get(role, field))
    return Commit.create_from_tree(
        repo,
        repo.tree(tree),
        message,
        parent_commits=[repo.commit(parent) for parent in dict.fromkeys(parents) if parent],
        head=False,
        author=author,
        committer=committer,
        author_date=_commit_date("GIT_AUTHOR_DATE"),
        commit_date=_commit_date("GIT_COMMITTER_DATE"),
    ).hexsha


def _get_branch_tip(repo_path: Path, branch: str) -> str | None:
    """Get the current commit hash of a branch, or None if it doesn't exist."""
    return _get_ref(repo_path, f"refs/heads/{branch}")


def _get_ref(repo_path: Path, ref: str) -> str | None:
    """Get the commit hash for any ref, or None if it doesn't exist."""
    repo = Repo(repo_path, odbt=GitDB)
    try:
        return SymbolicReference.dereference_recursive(repo, ref)
    except ValueError:
        return None


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
    return Repo(repo_path, odbt=GitDB).commit(commit).committed_date


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
    repo = Repo(repo_path, odbt=GitDB)
    our_temp_commit = _write_commit(repo, our_tree, [base_commit], "temp merge commit")

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
    """Replace conflicted paths with the winner's versions, preserving clean edits."""
    repo = Repo(repo_path, odbt=GitDB)
    winner = repo.tree(winner_commit)
    updates = {}
    for path in conflict_paths:
        try:
            entry = winner[path]
        except KeyError:
            updates[path] = None
        else:
            updates[path] = (f"{entry.mode:06o}", entry.hexsha)
    return _update_tree(repo_path, merged_tree, updates)


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
    repo = Repo(repo_path, odbt=GitDB)
    tree = repo.tree(treeish)
    tree.path = ""
    return {obj.path: (f"{obj.mode:06o}", obj.hexsha) for obj in tree.traverse() if obj.type == "blob"}


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
    repo = Repo(repo_path, odbt=GitDB)
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

    return _update_tree(repo_path, merged_tree, updates)


def _update_tree(repo_path: Path, tree: str, updates: dict[str, tuple[str, str] | None]) -> str:
    """Apply path updates in-process, rebuilding only affected subtrees.

    None removes a path. Untouched entries keep their object IDs and modes;
    directories emptied by a deletion disappear as they do in a Git index.
    """
    if not updates:
        return tree
    repo = Repo(repo_path, odbt=GitDB)

    def rebuild(tree_sha, changes):
        entries = {}
        if tree_sha:
            old_tree = repo.tree(tree_sha)
            old_tree.path = ""
            entries = {entry.name: (f"{entry.mode:06o}", entry.type, entry.hexsha, entry.name) for entry in old_tree}
        subtrees = {}
        for path, value in changes.items():
            name, separator, rest = path.partition("/")
            if separator:
                subtrees.setdefault(name, {})[rest] = value
            elif value is None:
                entries.pop(name, None)
            else:
                mode, sha = value
                kind = "tree" if int(mode, 8) == 0o40000 else "commit" if int(mode, 8) == 0o160000 else "blob"
                entries[name] = (mode, kind, sha, name)
        for name, children in subtrees.items():
            old = entries.get(name)
            child_sha, empty = rebuild(old[2] if old and old[1] == "tree" else None, children)
            if empty:
                entries.pop(name, None)
            else:
                entries[name] = ("040000", "tree", child_sha, name)
        return _mktree(repo, list(entries.values())), not entries

    return rebuild(tree, updates)[0]


# --- Section-level card merging ---

_TASK_STATE_RE = re.compile(r"^(\s*- \[)([ xX])(\] .*)$")


def _merge_meta(base: dict, older: dict, newer: dict) -> dict:
    """Per-key 3-way merge; a key changed on both sides takes the newer value."""
    merged: dict = {}
    keys = list(newer.keys()) + [k for k in older.keys() if k not in newer]
    for key in keys:
        base_val = base.get(key)
        older_val = older.get(key)
        newer_val = newer.get(key)
        if older_val == base_val:
            value = newer_val
        elif newer_val == base_val:
            value = older_val
        else:
            value = newer_val
        if value is not None:
            merged[key] = value
    return merged


def _merge_task_states(base: str, older: str, newer: str) -> str | None:
    """Merge checkbox toggles when both sides only flipped states.

    Returns None unless both sides have the same lines as base modulo
    [ ]/[x] markers — structural edits fall through to the other tiers.
    """
    base_lines = base.split("\n")
    older_lines = older.split("\n")
    newer_lines = newer.split("\n")

    def shape(lines: list[str]) -> list[str]:
        return [_TASK_STATE_RE.sub(r"\1_\3", line) for line in lines]

    if shape(older_lines) != shape(base_lines) or shape(newer_lines) != shape(base_lines):
        return None

    merged = []
    for base_line, older_line, newer_line in zip(base_lines, older_lines, newer_lines):
        if older_line == base_line:
            merged.append(newer_line)
        elif newer_line == base_line:
            merged.append(older_line)
        else:
            merged.append(newer_line)
    return "\n".join(merged)


def _merge_bodies(base: str, older: str, newer: str) -> str:
    """Merge one section body that both sides changed.

    Tiers: checkbox-state merge, then append-concatenation (both sides
    grew the same base — comments and additive edits; the older side's
    suffix comes first so e.g. comment threads stay chronological), then
    newer-wins for genuinely overlapping edits.
    """
    task_merged = _merge_task_states(base, older, newer)
    if task_merged is not None:
        return task_merged

    if older.startswith(base) and newer.startswith(base):
        pieces = [base] if base else []
        for suffix in (older[len(base) :], newer[len(base) :]):
            suffix = suffix.strip("\n")
            if suffix:
                pieces.append(suffix)
        separator = "\n" if all(p.lstrip().startswith(("-", "*")) for p in pieces) else "\n\n"
        return separator.join(pieces)

    return newer


def _merge_card_texts(base_text: str, older_text: str, newer_text: str) -> str:
    """3-way merge a card at section granularity.

    Sections changed on one side only are taken as-is; a section deleted
    on one side and edited on the other follows the newer side's action;
    bodies changed on both sides go through _merge_bodies. Section order
    follows the newer side, with the older side's additions appended.
    """
    base_sections, base_meta = parse_sections(base_text)
    older_sections, older_meta = parse_sections(older_text)
    newer_sections, newer_meta = parse_sections(newer_text)

    meta = _merge_meta(base_meta or {}, older_meta or {}, newer_meta or {})

    base_map = dict(base_sections)
    older_map = dict(older_sections)
    newer_map = dict(newer_sections)

    titles = [t for t, _ in newer_sections]
    titles += [t for t, _ in older_sections if t not in newer_map]

    merged_sections: list[tuple[str, str]] = []
    for title in titles:
        base_body = base_map.get(title)
        older_body = older_map.get(title)
        newer_body = newer_map.get(title)

        if older_body == newer_body:
            body = older_body
        elif older_body == base_body:
            body = newer_body
        elif newer_body == base_body:
            body = older_body
        elif newer_body is None or older_body is None:
            body = newer_body  # delete vs edit: the newer side's action wins
        else:
            body = _merge_bodies(base_body or "", older_body, newer_body)

        if body is not None:
            merged_sections.append((title, body))

    return serialize_sections(merged_sections, meta or None)


def _merge_card_conflicts(
    repo_path: Path,
    merge_info: MergeRequired,
    merged_tree: str,
    paths: list[str],
    ours_newer: bool,
) -> tuple[str, list[str]]:
    """Resolve edit/edit conflicts on card files by section-level merging.

    Returns (new_tree, leftover_paths); leftovers are card conflicts this
    can't handle (e.g. modify/delete) for most-recent-wins to resolve.
    """
    repo = Repo(repo_path, odbt=GitDB)
    base_paths = _tree_paths(repo_path, merge_info.base)
    ours_paths = _tree_paths(repo_path, merge_info.ours)
    theirs_paths = _tree_paths(repo_path, merge_info.theirs)

    updates: dict[str, tuple[str, str]] = {}
    leftovers: list[str] = []
    for path in paths:
        base_entry = base_paths.get(path)
        ours_entry = ours_paths.get(path)
        theirs_entry = theirs_paths.get(path)
        if not (base_entry and ours_entry and theirs_entry):
            leftovers.append(path)
            continue
        base_text = _read_blob(repo, base_entry[1])
        ours_text = _read_blob(repo, ours_entry[1])
        theirs_text = _read_blob(repo, theirs_entry[1])
        older_text, newer_text = (theirs_text, ours_text) if ours_newer else (ours_text, theirs_text)
        merged_text = _merge_card_texts(base_text, older_text, newer_text)
        updates[path] = ("100644", _write_blob(repo, merged_text))

    return _update_tree(repo_path, merged_tree, updates), leftovers


# --- Board tree building ---


def _build_board_tree(repo: Repo, board: Node) -> str:
    """Build the complete git tree for a board and return its hash."""
    # Build card blobs and .all tree
    width = max(max((len(cid) for cid in board.cards.keys()), default=1), 3)
    card_entries = []
    for card_id, card in board.cards.items():
        text = sections_to_text(card.sections, card.meta)
        blob = _write_blob(repo, text)
        card_entries.append(("100644", "blob", blob, f"{pad_id(card_id, width)}.md"))

    all_tree = _mktree(repo, card_entries)

    # Build column trees
    column_trees = []
    for col in board.columns:
        col_tree = _build_column_tree(repo, col, board, width)
        column_trees.append((col.dir_path, col_tree))

    # Build root tree entries
    root_entries = [("040000", "tree", all_tree, ".all")]

    for dir_path, tree_sha in column_trees:
        root_entries.append(("040000", "tree", tree_sha, dir_path))

    index_blob = _write_blob(repo, sections_to_text(board.sections, board.meta))
    root_entries.append(("100644", "blob", index_blob, "index.md"))

    return _mktree(repo, root_entries)


def _build_column_tree(repo: Repo, col: Node, board: Node, width: int = 3) -> str:
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

    return _mktree(repo, entries)


# --- Public API ---


def save_board(
    board: Node,
    message: str = "Update board",
    branch: str = BRANCH_NAME,
    parents: list[str] | None = None,
) -> str:
    """Save a board to git and return the new commit hash."""
    repo_path = Path(board.repo_path)
    repo = Repo(repo_path, odbt=GitDB)

    tree = _build_board_tree(repo, board)

    if parents is None:
        if board.commit:
            parents = [board.commit]
        else:
            current_tip = _get_branch_tip(repo_path, branch)
            parents = [current_tip] if current_tip else []

    # Skip commit if tree is unchanged from parent
    if len(parents) == 1 and parents[0]:
        parent_tree = repo.commit(parents[0]).tree.hexsha
        if parent_tree == tree:
            return board.commit

    new_commit = _write_commit(repo, tree, parents, message)

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

    repo = Repo(repo_path, odbt=GitDB)
    our_tree = _build_board_tree(repo, board)

    # Fast-forward: our tree matches the merge base, so we're just behind
    base_tree = repo.commit(merge_info.base).tree.hexsha
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
        remaining = [p for p in conflict_paths if p not in collision_paths]

        # Newer side by (committer ts, sha) — the sha tiebreak keeps the
        # outcome identical no matter which replica performs the merge
        ours_key = (_commit_timestamp(repo_path, merge_info.ours), merge_info.ours)
        theirs_key = (_commit_timestamp(repo_path, merge_info.theirs), merge_info.theirs)
        ours_newer = ours_key >= theirs_key

        # Cards edited on both sides merge at section granularity
        card_paths = [p for p in remaining if _CARD_PATH_RE.match(p)]
        other_paths = [p for p in remaining if not _CARD_PATH_RE.match(p)]
        if card_paths:
            merged_tree, leftovers = _merge_card_conflicts(repo_path, merge_info, merged_tree, card_paths, ours_newer)
            other_paths += leftovers

        if other_paths:
            # Most-recent-commit-wins: replace only the conflicted files.
            # Non-conflicting changes from both sides are preserved in merged_tree.
            winner = merge_info.ours if ours_newer else merge_info.theirs
            merged_tree = _resolve_conflicts(repo_path, merged_tree, winner, other_paths)

        if collisions:
            merged_tree = _resolve_id_collisions(repo_path, merge_info, merged_tree, collisions)

    new_commit = _write_commit(repo, merged_tree, [merge_info.ours, merge_info.theirs], message)

    if not _update_ref_cas(repo_path, branch, new_commit, tip):
        return None

    return new_commit
