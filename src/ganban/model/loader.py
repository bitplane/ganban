"""Load a ganban board from git into a Node tree."""

import re
import subprocess
from datetime import datetime, timezone
from functools import cmp_to_key

from git import Repo
from git.objects import Blob, Tree

from ganban.git import read_git_config
from ganban.ids import compare_ids, max_id, next_id, normalize_id
from ganban.constants import BRANCH_NAME
from ganban.model.node import ListNode, Node
from ganban.parser import parse_sections
from ganban.palette import color_for_label

MAX_COMMITS = 100


def _tree_get(tree: Tree, name: str) -> Blob | Tree | None:
    """Get an item from a tree by name, returning None if not found."""
    try:
        return tree[name]
    except KeyError:
        return None


def _split_prefixed_name(name: str) -> tuple[str, str] | None:
    """Split 'prefix.rest' into (prefix, rest) or None if no dot."""
    match = re.match(r"^([^.]+)\.(.+)$", name)
    return (match.group(1), match.group(2)) if match else None


def _parse_dirname(name: str) -> tuple[str | None, str, bool]:
    """Parse a directory name into (order, name, hidden).

    Examples:
        "1.backlog" -> ("1", "Backlog", False)
        ".all" -> (None, "all", True)  # Hidden but not a column
        "2.in-progress" -> ("2", "In progress", False)
    """
    hidden = name.startswith(".")
    if hidden:
        name = name[1:]

    parts = _split_prefixed_name(name)
    if not parts:
        return None, name, hidden

    order, slug = parts

    normalized = slug.replace("-", " ").replace("_", " ")
    normalized = normalized[0].upper() + normalized[1:] if normalized else ""

    return order, normalized, hidden


def _parse_link_name(name: str) -> tuple[str | None, str]:
    """Parse a symlink filename into (position, slug).

    Examples:
        "01.fix-login-bug.md" -> ("01", "fix-login-bug")
        "readme.md" -> (None, "readme")
    """
    stem = name[:-3] if name.endswith(".md") else name

    parts = _split_prefixed_name(stem)
    if not parts:
        return None, stem

    return parts


def _build_sections_list(text: str, fallback_title: str = "Untitled") -> tuple[ListNode, dict]:
    """Parse markdown text into a ListNode of sections plus meta dict.

    If the first section has no title, fallback_title is used.
    """
    sections, meta = parse_sections(text)
    ln = ListNode()
    for i, (title, body) in enumerate(sections):
        if not title and i == 0:
            title = fallback_title
        ln.add(title, body)
    return ln, meta


def _get_committers(repo: Repo, max_count: int = MAX_COMMITS) -> list[str]:
    """Extract unique committers from recent git history.

    Returns a sorted list of "Name <email>" strings.
    """
    seen: set[str] = set()
    for commit in repo.iter_commits(max_count=max_count, all=True):
        seen.add(f"{commit.author.name} <{commit.author.email}>")
    return sorted(seen)


def file_creation_date(repo_path: str, file_path: str, branch: str = BRANCH_NAME) -> datetime | None:
    """Get the author date of the commit that first added a file on a branch.

    Returns None if the file has no history on the branch.
    """
    result = subprocess.run(
        [
            "git",
            "log",
            "--diff-filter=A",
            "--reverse",
            "--format=%aI",
            branch,
            "--",
            file_path,
        ],
        cwd=repo_path,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    first_line = result.stdout.decode("utf-8").strip().split("\n")[0]
    if not first_line:
        return None
    return datetime.fromisoformat(first_line).astimezone(timezone.utc)


def _load_tree(tree: Tree) -> Node:
    """Deserialize a ganban branch tree into a Node.

    Pure data loading — no repo_path, commit, or git node attached.
    """
    board = Node()

    # Root index.md
    index_blob = _tree_get(tree, "index.md")
    if index_blob is not None:
        text = index_blob.data_stream.read().decode("utf-8")
        sections_ln, meta = _build_sections_list(text, fallback_title="ganban")
        board.sections = sections_ln
        board.meta = meta
    else:
        board.sections = ListNode()
        board.sections["ganban"] = ""
        board.meta = {}

    # Load all cards from .all/
    cards_ln = ListNode()
    all_tree = _tree_get(tree, ".all")
    card_ids: set[str] = set()
    if isinstance(all_tree, Tree):
        for item in all_tree:
            if not isinstance(item, Blob):
                continue
            if not item.name.endswith(".md"):
                continue
            card_id = normalize_id(item.name[:-3])
            card_ids.add(card_id)
            text = item.data_stream.read().decode("utf-8")
            sections_ln, meta = _build_sections_list(text, fallback_title=card_id)
            card = Node(
                sections=sections_ln,
                meta=meta,
            )
            cards_ln[card_id] = card
    board.cards = cards_ln

    # Load columns
    columns_ln = ListNode()
    col_entries: list[tuple[str, str, str, bool, Tree]] = []
    for item in tree:
        if not isinstance(item, Tree):
            continue
        order, name, hidden = _parse_dirname(item.name)
        if order is None:
            continue
        col_entries.append((order, name, item.name, hidden, item))

    col_entries.sort(key=cmp_to_key(lambda a, b: compare_ids(a[0], b[0])))

    for order, name, dirname, hidden, col_tree in col_entries:
        col_meta: dict = {}

        index_blob = _tree_get(col_tree, "index.md")
        if index_blob is not None:
            text = index_blob.data_stream.read().decode("utf-8")
            col_sections, col_meta = _build_sections_list(text, fallback_title=name)
        else:
            col_sections = ListNode()
            col_sections[name] = ""

        # Build links list
        link_entries: list[tuple[str, str]] = []
        for link_item in col_tree:
            if link_item.type != "blob":
                continue
            if not link_item.name.endswith(".md"):
                continue
            if link_item.name == "index.md":
                continue
            position, slug = _parse_link_name(link_item.name)
            if position is None:
                continue
            if link_item.mode == 0o120000:
                target = link_item.data_stream.read().decode("utf-8")
                card_id = target.split("/")[-1]
                if card_id.endswith(".md"):
                    card_id = normalize_id(card_id[:-3])
                if card_id not in card_ids:
                    continue
            else:
                # Regular file: adopt as a new card
                card_id = next_id(max_id(list(card_ids)))
                card_ids.add(card_id)
                text = link_item.data_stream.read().decode("utf-8")
                sections_ln, meta = _build_sections_list(text, fallback_title=slug)
                card = Node(
                    sections=sections_ln,
                    meta=meta,
                )
                cards_ln[card_id] = card
            link_entries.append((position, card_id))

        link_entries.sort(key=cmp_to_key(lambda a, b: compare_ids(a[0], b[0])))
        links = tuple(card_id for _, card_id in link_entries)

        col = Node(
            order=order,
            dir_path=dirname,
            hidden=hidden,
            sections=col_sections,
            meta=col_meta,
            links=links,
        )
        columns_ln[order] = col

    board.columns = columns_ln
    return board


def _on_board_card_ids(board: Node) -> set[str]:
    """Return the set of card IDs that appear in any column's links."""
    on_board: set[str] = set()
    for col in board.columns:
        on_board.update(col.links)
    return on_board


def _setup_archived(board: Node) -> None:
    """Set card.archived for each card and watch columns to keep it in sync."""
    on_board = _on_board_card_ids(board)
    for card_id, card in board.cards.items():
        card.archived = card_id not in on_board

    def on_links_changed(source_node, key, old, new):
        old_set = set(old) if old else set()
        new_set = set(new) if new else set()
        for card_id in old_set - new_set:
            card = board.cards[card_id]
            if card is not None:
                card.archived = card_id not in _on_board_card_ids(board)
        for card_id in new_set - old_set:
            card = board.cards[card_id]
            if card is not None:
                card.archived = False

    for col in board.columns:
        col.watch("links", on_links_changed)


def _is_ready(card: Node) -> bool:
    """A card is ready if it's archived or marked done."""
    return card.archived or bool(card.meta and card.meta.done)


def _recompute_blocked(board: Node) -> None:
    """Set or clear card.blocked for every card based on its deps."""
    for card_id, card in board.cards.items():
        deps = card.meta.deps if card.meta else None
        if not deps:
            card.blocked = None
            continue
        blocked = any(not _is_ready(board.cards[dep_id]) for dep_id in deps if board.cards[dep_id] is not None)
        card.blocked = True if blocked else None


def _setup_blocked(board: Node) -> None:
    """Compute card.blocked and watch for changes that affect it."""
    _recompute_blocked(board)

    def on_cards_changed(source_node, key, old, new):
        if key == "archived" and source_node._parent is board.cards:
            _recompute_blocked(board)
        elif key in ("done", "deps") and source_node._key == "meta" and source_node._parent._parent is board.cards:
            _recompute_blocked(board)

    board.watch("cards", on_cards_changed)


def normalise_label(raw: str) -> str:
    """Normalise a label name to lowercase, stripped."""
    return raw.strip().lower()


def _build_labels_index(board: Node) -> dict[str, Node]:
    """Build {label_name: Node(color=..., cards=[...])} from current state."""
    index: dict[str, list[str]] = {}

    # Collect from all cards
    for card_id, card in board.cards.items():
        labels = card.meta.labels if card.meta else None
        if not isinstance(labels, list):
            continue
        for raw in labels:
            name = normalise_label(raw)
            if name:
                index.setdefault(name, []).append(card_id)

    # Collect from board meta (may add labels with no cards)
    meta_labels = board.meta.labels if board.meta else None
    if meta_labels and isinstance(meta_labels, Node):
        for name in meta_labels.keys():
            norm = normalise_label(name)
            if norm:
                index.setdefault(norm, [])

    # Build nodes with resolved colours
    result = {}
    for name, card_ids in index.items():
        override = None
        if meta_labels and isinstance(meta_labels, Node):
            entry = getattr(meta_labels, name, None)
            if entry and isinstance(entry, Node):
                override = entry.color
        color = override or color_for_label(name)
        result[name] = Node(color=color, cards=card_ids)
    return result


def _recompute_labels(board: Node) -> None:
    """Recompute board.labels index in-place."""
    new_index = _build_labels_index(board)
    existing = board.labels

    # Remove labels that no longer exist
    for key in list(existing.keys()):
        if key not in new_index:
            setattr(existing, key, None)

    # Update/add labels
    for name, node in new_index.items():
        old = getattr(existing, name)
        if old is None:
            setattr(existing, name, node)
        else:
            old.color = node.color
            old.cards = node.cards


def _setup_labels(board: Node) -> None:
    """Build board.labels index and watch for changes."""
    board.labels = Node(**_build_labels_index(board))

    def on_cards_changed(source_node, key, old, new):
        if key == "labels":
            _recompute_labels(board)
        elif key == "*" and source_node is board.cards:
            _recompute_labels(board)

    def on_board_meta_labels_changed(source_node, key, old, new):
        _recompute_labels(board)

    board.watch("cards", on_cards_changed)
    if board.meta:
        board.meta.watch("labels", on_board_meta_labels_changed)


def _activate(board: Node, repo: Repo) -> None:
    """Attach computed/derived properties to a loaded board."""
    config_dict = read_git_config(board.repo_path)
    config_node = Node(**{section: Node(**keys) for section, keys in config_dict.items()})
    board.git = Node(committers=_get_committers(repo), config=config_node)
    _setup_archived(board)
    _setup_blocked(board)
    _setup_labels(board)


def load_board(repo_path: str, branch: str = BRANCH_NAME) -> Node:
    """Load a complete board from a git branch as a Node tree."""
    repo = Repo(repo_path)

    try:
        commit = repo.commit(branch)
    except Exception:
        raise ValueError(f"Branch '{branch}' not found in repository")

    board = _load_tree(commit.tree)
    board.repo_path = str(repo_path)
    board.commit = commit.hexsha
    _activate(board, repo)
    return board
