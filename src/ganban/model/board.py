"""Board-level helpers."""

from pathlib import Path

from ganban.model.column import create_column
from ganban.model.node import ListNode, Node


def create_default_board(repo_path: str | Path) -> Node:
    """Build the default board (Backlog/Doing/Done) for a new repository."""
    repo_path = Path(repo_path)
    board = Node(repo_path=str(repo_path))
    board.sections = ListNode()
    board.sections[repo_path.name] = ""
    board.meta = {}
    board.cards = ListNode()
    board.columns = ListNode()
    backlog = create_column(board, "Backlog", order="1")
    backlog.meta.compact = True
    create_column(board, "Doing", order="2")
    create_column(board, "Done", order="3")
    return board
