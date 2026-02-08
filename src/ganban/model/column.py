"""Column mutation operations for ganban boards."""

import re

from ganban.ids import max_id, next_id
from ganban.model.node import ListNode, Node
from ganban.parser import first_title


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


def move_column(board: Node, column: Node, new_index: int) -> None:
    """Move column to new_index in the board's columns ListNode.

    Rebuilds the columns ListNode with updated order values and dir_paths.
    """
    all_cols = list(board.columns)
    all_cols.remove(column)
    all_cols.insert(new_index, column)

    old_keys = board.columns.keys()
    for key in old_keys:
        board.columns[key] = None

    for i, col in enumerate(all_cols):
        col.order = str(i + 1)
        col.dir_path = build_column_path(col.order, first_title(col.sections), col.hidden)
        board.columns[col.order] = col


def archive_column(board: Node, column_order: str) -> None:
    """Archive a column by removing it from the board."""
    board.columns[column_order] = None


def rename_column(board: Node, column: Node, new_name: str) -> None:
    """Rename a column: update its sections title and dir_path."""
    column.sections.rename_first_key(new_name)
    column.dir_path = build_column_path(column.order, new_name, column.hidden)
