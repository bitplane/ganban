"""Load a ganban board from git tree."""

import asyncio
import re
from functools import cmp_to_key

from git import Repo

from ganban.ids import compare_ids
from git.objects import Blob, Tree

from ganban.models import Board, Card, CardLink, Column, MarkdownDoc
from ganban.parser import parse_markdown

BRANCH_NAME = "ganban"


def _tree_get(tree: Tree, name: str) -> Blob | Tree | None:
    """Get an item from a tree by name, returning None if not found.

    GitPython's `in` operator doesn't work reliably on subtrees,
    so we use direct access with exception handling.
    """
    try:
        return tree[name]
    except KeyError:
        return None


async def load_board(repo_path: str, branch: str = BRANCH_NAME) -> Board:
    """Load a complete board from a git branch."""
    return await asyncio.to_thread(_load_board_sync, repo_path, branch)


def _load_board_sync(repo_path: str, branch: str) -> Board:
    """Synchronous implementation of load_board."""
    repo = Repo(repo_path)

    # Get the branch commit
    try:
        commit = repo.commit(branch)
    except Exception:
        raise ValueError(f"Branch '{branch}' not found in repository")

    tree = commit.tree

    board = Board(repo_path=repo_path, commit=commit.hexsha)

    # Load root index.md if present
    index_blob = _tree_get(tree, "index.md")
    if index_blob is not None:
        board.content = _load_markdown_doc(index_blob)

    # Load all cards from .all/
    all_tree = _tree_get(tree, ".all")
    if isinstance(all_tree, Tree):
        board.cards = _load_cards(all_tree)

    # Load columns
    board.columns = _load_columns(tree, board.cards)

    return board


def _load_markdown_doc(blob: Blob) -> MarkdownDoc:
    """Load and parse a markdown file from a git blob."""
    text = blob.data_stream.read().decode("utf-8")
    return parse_markdown(text)


def _load_cards(all_tree: Tree) -> dict[str, Card]:
    """Load all cards from the .all/ tree."""
    cards = {}

    for item in all_tree:
        if not isinstance(item, Blob):
            continue
        if not item.name.endswith(".md"):
            continue

        card_id = item.name[:-3]  # Remove .md
        card = Card(
            id=card_id,
            path=f".all/{item.name}",
            content=_load_markdown_doc(item),
        )
        cards[card_id] = card

    return cards


def _load_columns(tree: Tree, cards: dict[str, Card]) -> list[Column]:
    """Load all column directories from the tree."""
    columns = []

    for item in tree:
        if not isinstance(item, Tree):
            continue

        # Parse directory name for order and name
        order, name, hidden = _parse_dirname(item.name)
        if order is None:
            continue  # Not a column directory

        column = Column(
            order=order,
            name=name,
            path=item.name,
            hidden=hidden,
            content=MarkdownDoc(),
        )

        # Load index.md if present
        index_blob = _tree_get(item, "index.md")
        if index_blob is not None:
            column.content = _load_markdown_doc(index_blob)
            if column.content.title:
                column.name = column.content.title

        # Load card links (symlinks in git are blobs with mode 120000)
        column.links = _load_card_links(item, cards)

        columns.append(column)

    columns.sort(key=cmp_to_key(lambda a, b: compare_ids(a.order, b.order)))
    return columns


def _split_prefixed_name(name: str) -> tuple[str, str] | None:
    """Split 'prefix.rest' into (prefix, rest) or None if no dot."""
    match = re.match(r"^([^.]+)\.(.+)$", name)
    return (match.group(1), match.group(2)) if match else None


def _load_card_links(column_tree: Tree, cards: dict[str, Card]) -> list[CardLink]:
    """Load card symlinks from a column tree."""
    links = []

    for item in column_tree:
        # In git, symlinks are blobs with mode 120000 (0o120000)
        if item.type != "blob":
            continue
        if item.mode != 0o120000:
            continue
        if not item.name.endswith(".md"):
            continue

        position, slug = _parse_link_name(item.name)
        if position is None:
            continue

        # Symlink target is the blob content
        target = item.data_stream.read().decode("utf-8")
        # Extract card ID from target path like "../.all/001.md"
        card_id = target.split("/")[-1]
        if card_id.endswith(".md"):
            card_id = card_id[:-3]

        broken = card_id not in cards

        link = CardLink(
            position=position,
            slug=slug,
            card_id=card_id,
            path=f"{column_tree.name}/{item.name}",
            broken=broken,
        )
        links.append(link)

    links.sort(key=cmp_to_key(lambda a, b: compare_ids(a.position, b.position)))
    return links


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
