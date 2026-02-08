"""Load a ganban board from git into a Node tree."""

import re
from functools import cmp_to_key

from git import Repo
from git.objects import Blob, Tree

from ganban.ids import compare_ids, max_id, next_id
from ganban.model.node import BRANCH_NAME, ListNode, Node
from ganban.parser import parse_sections

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
        ln[title] = body
    return ln, meta


def _get_committers(repo: Repo, max_count: int = MAX_COMMITS) -> list[str]:
    """Extract unique committers from recent git history.

    Returns a sorted list of "Name <email>" strings.
    """
    seen: set[str] = set()
    for commit in repo.iter_commits(max_count=max_count, all=True):
        seen.add(f"{commit.author.name} <{commit.author.email}>")
    return sorted(seen)


def load_board(repo_path: str, branch: str = BRANCH_NAME) -> Node:
    """Load a complete board from a git branch as a Node tree."""
    repo = Repo(repo_path)

    try:
        commit = repo.commit(branch)
    except Exception:
        raise ValueError(f"Branch '{branch}' not found in repository")

    tree = commit.tree
    board = Node(repo_path=str(repo_path), commit=commit.hexsha)

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
            card_id = item.name[:-3]
            card_ids.add(card_id)
            text = item.data_stream.read().decode("utf-8")
            sections_ln, meta = _build_sections_list(text, fallback_title=card_id)
            card = Node(
                sections=sections_ln,
                meta=meta,
                file_path=f".all/{item.name}",
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
        links: list[str] = []
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
                    card_id = card_id[:-3]
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
                    file_path=f".all/{card_id}.md",
                )
                cards_ln[card_id] = card
            link_entries.append((position, card_id))

        link_entries.sort(key=cmp_to_key(lambda a, b: compare_ids(a[0], b[0])))
        links = [card_id for _, card_id in link_entries]

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
    board.git = Node(committers=_get_committers(repo))
    return board
