"""Handlers for 'ganban board' commands."""

import sys

from ganban.cli._common import (
    load_board_or_die,
    markdown_to_sections,
    meta_to_dict,
    output_json,
    save,
    sections_to_markdown,
)
from ganban.parser import first_title


def board_summary(args) -> int:
    """Show board summary: title, columns, card counts."""
    board = load_board_or_die(args.repo, args.json)
    title = first_title(board.sections)

    columns = []
    for col in board.columns:
        name = first_title(col.sections)
        card_count = len(col.links) if col.links else 0
        columns.append(
            {
                "id": col.order,
                "name": name,
                "cards": card_count,
                "hidden": bool(col.hidden),
            }
        )

    if args.json:
        output_json({"title": title, "columns": columns})
    else:
        print(title)
        for c in columns:
            hidden = "  (hidden)" if c["hidden"] else ""
            cards = "card" if c["cards"] == 1 else "cards"
            print(f"  {c['id']}  {c['name']:<16} {c['cards']} {cards}{hidden}")

    return 0


def board_get(args) -> int:
    """Dump board index.md content."""
    board = load_board_or_die(args.repo, args.json)

    markdown = sections_to_markdown(board.sections, board.meta)

    if args.json:
        output_json(
            {
                "title": first_title(board.sections),
                "meta": meta_to_dict(board.meta),
                "markdown": markdown,
            }
        )
    else:
        sys.stdout.write(markdown)

    return 0


def board_set(args) -> int:
    """Write board index.md from stdin."""
    board = load_board_or_die(args.repo, args.json)

    text = sys.stdin.read()
    new_sections, new_meta = markdown_to_sections(text)

    # Replace board sections and meta
    board.sections = new_sections
    board.meta = new_meta

    commit = save(board, "Update board")

    if args.json:
        output_json({"commit": commit})
    else:
        print(f"Updated board ({commit[:7]})")

    return 0
