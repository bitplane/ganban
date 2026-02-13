"""Shared helpers for CLI command handlers."""

import json
import sys
from pathlib import Path

from ganban.model.loader import load_board
from ganban.model.node import ListNode, Node
from ganban.model.writer import save_board
from ganban.parser import first_title, parse_sections


def load_board_or_die(repo: str, json_mode: bool) -> Node:
    """Load board from repo path. Exit 1 with message if not found."""
    repo_path = Path(repo).resolve()
    try:
        return load_board(str(repo_path))
    except Exception as e:
        error(str(e), json_mode)


def find_column(board: Node, col_id: str, json_mode: bool) -> Node:
    """Lookup column by order ID. Exit 1 listing available columns if not found."""
    col = board.columns[col_id]
    if col is not None:
        return col
    available = [f"  {k}  {first_title(c.sections)}" for k, c in board.columns.items()]
    msg = f"Column '{col_id}' not found. Available:\n" + "\n".join(available)
    error(msg, json_mode)


def find_card(board: Node, card_id: str, json_mode: bool) -> Node:
    """Lookup card by ID. Exit 1 if not found."""
    card = board.cards[card_id]
    if card is not None:
        return card
    error(f"Card '{card_id}' not found.", json_mode)


def save(board: Node, message: str) -> str:
    """Save board and return commit hash."""
    commit = save_board(board, message=message)
    board.commit = commit
    return commit


def output_json(data: dict | list) -> None:
    """Write JSON to stdout."""
    print(json.dumps(data, indent=2))


def output_result(data: dict, text: str, json_mode: bool) -> None:
    """Output mutation result as JSON or plain text."""
    if json_mode:
        output_json(data)
    else:
        print(text)


def error(message: str, json_mode: bool) -> None:
    """Print error to stderr and exit 1."""
    if json_mode:
        print(json.dumps({"error": message}), file=sys.stderr)
    else:
        print(f"error: {message}", file=sys.stderr)
    sys.exit(1)


def build_column_summaries(board: Node) -> list[dict]:
    """Build column summary dicts from board."""
    items = []
    for col in board.columns:
        name = first_title(col.sections)
        card_count = len(col.links) if col.links else 0
        items.append(
            {
                "id": col.order,
                "name": name,
                "cards": card_count,
                "hidden": bool(col.hidden),
            }
        )
    return items


def format_column_line(c: dict, indent: str = "") -> str:
    """Format a column summary dict as a text line."""
    hidden = "  (hidden)" if c["hidden"] else ""
    cards = "card" if c["cards"] == 1 else "cards"
    return f"{indent}{c['id']}  {c['name']:<16} {c['cards']} {cards}{hidden}"


def markdown_to_sections(text: str) -> tuple[ListNode, dict]:
    """Parse markdown text into (ListNode, meta_dict)."""
    sections_list, meta = parse_sections(text)
    sections = ListNode()
    for title, body in sections_list:
        sections.add(title, body)
    return sections, meta
