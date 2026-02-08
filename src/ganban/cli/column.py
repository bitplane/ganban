"""Handlers for 'ganban column' commands."""

import sys

from ganban.cli._common import (
    find_column,
    load_board_or_die,
    markdown_to_sections,
    meta_to_dict,
    output_json,
    save,
    sections_to_markdown,
)
from ganban.model.column import (
    archive_column,
    create_column,
    move_column,
    rename_column,
)
from ganban.parser import first_title


def column_list(args) -> int:
    """List all columns."""
    board = load_board_or_die(args.repo, args.json)

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

    if args.json:
        output_json(items)
    else:
        for c in items:
            hidden = "  (hidden)" if c["hidden"] else ""
            cards = "card" if c["cards"] == 1 else "cards"
            print(f"{c['id']}  {c['name']:<16} {c['cards']} {cards}{hidden}")

    return 0


def column_get(args) -> int:
    """Dump column index.md content."""
    board = load_board_or_die(args.repo, args.json)
    col = find_column(board, args.id, args.json)

    markdown = sections_to_markdown(col.sections, col.meta)

    if args.json:
        output_json(
            {
                "id": col.order,
                "name": first_title(col.sections),
                "meta": meta_to_dict(col.meta),
                "markdown": markdown,
            }
        )
    else:
        sys.stdout.write(markdown)

    return 0


def column_set(args) -> int:
    """Write column index.md from stdin."""
    board = load_board_or_die(args.repo, args.json)
    col = find_column(board, args.id, args.json)

    text = sys.stdin.read()
    new_sections, new_meta = markdown_to_sections(text)

    col.sections = new_sections
    col.meta = new_meta

    name = first_title(new_sections)
    commit = save(board, f"Update column {col.order}: {name}")

    if args.json:
        output_json({"id": col.order, "commit": commit})
    else:
        print(f"Updated column {col.order} ({commit[:7]})")

    return 0


def column_add(args) -> int:
    """Create a new column."""
    board = load_board_or_die(args.repo, args.json)

    col = create_column(board, args.name, hidden=args.hidden)

    commit = save(board, f"Add column: {args.name}")

    if args.json:
        output_json(
            {
                "id": col.order,
                "name": args.name,
                "hidden": args.hidden,
                "commit": commit,
            }
        )
    else:
        print(f'Created column "{args.name}" (id {col.order}) ({commit[:7]})')

    return 0


def column_move(args) -> int:
    """Move a column to a new position."""
    board = load_board_or_die(args.repo, args.json)
    col = find_column(board, args.id, args.json)

    # CLI uses 1-indexed positions, model uses 0-indexed
    new_index = args.position - 1

    move_column(board, col, new_index)

    name = first_title(col.sections)
    commit = save(board, f"Move column {name} to position {args.position}")

    if args.json:
        output_json(
            {
                "id": col.order,
                "name": name,
                "position": args.position,
                "commit": commit,
            }
        )
    else:
        print(f'Moved column "{name}" to position {args.position} ({commit[:7]})')

    return 0


def column_rename(args) -> int:
    """Rename a column."""
    board = load_board_or_die(args.repo, args.json)
    col = find_column(board, args.id, args.json)

    old_name = first_title(col.sections)
    rename_column(board, col, args.new_name)

    commit = save(board, f'Rename column "{old_name}" to "{args.new_name}"')

    if args.json:
        output_json(
            {
                "id": col.order,
                "old_name": old_name,
                "new_name": args.new_name,
                "commit": commit,
            }
        )
    else:
        print(f'Renamed column "{old_name}" to "{args.new_name}" ({commit[:7]})')

    return 0


def column_archive(args) -> int:
    """Archive a column."""
    board = load_board_or_die(args.repo, args.json)
    col = find_column(board, args.id, args.json)

    name = first_title(col.sections)
    archive_column(board, args.id)

    commit = save(board, f"Archive column {name}")

    if args.json:
        output_json({"id": args.id, "name": name, "commit": commit})
    else:
        print(f'Archived column "{name}" ({commit[:7]})')

    return 0
