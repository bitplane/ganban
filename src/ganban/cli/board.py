"""Handlers for 'ganban board' commands."""

import sys

from ganban.cli._common import (
    build_column_summaries,
    format_column_line,
    load_board_or_die,
    markdown_to_sections,
    output_json,
    output_result,
    save,
)
from ganban.model.writer import meta_to_dict, sections_to_text
from ganban.parser import first_title


def board_summary(args) -> int:
    """Show board summary: title, columns, card counts."""
    board = load_board_or_die(args.repo, args.json)
    title = first_title(board.sections)

    columns = build_column_summaries(board)

    if args.json:
        output_json({"title": title, "columns": columns})
    else:
        print(title)
        for c in columns:
            print(format_column_line(c, indent="  "))

    return 0


def board_get(args) -> int:
    """Dump board index.md content."""
    board = load_board_or_die(args.repo, args.json)

    markdown = sections_to_text(board.sections, board.meta)

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

    board.sections = new_sections
    board.meta = new_meta

    commit = save(board, "Update board")

    output_result({"commit": commit}, f"Updated board ({commit[:7]})", args.json)

    return 0
