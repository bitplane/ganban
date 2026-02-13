"""Handlers for 'ganban card' commands."""

import sys

from ganban.cli._common import (
    find_card,
    find_column,
    load_board_or_die,
    markdown_to_sections,
    output_json,
    output_result,
    save,
)
from ganban.ids import normalize_id
from ganban.model.card import archive_card, create_card, find_card_column, move_card
from ganban.model.writer import meta_to_dict, sections_to_text
from ganban.parser import first_title


def card_list(args) -> int:
    """List cards grouped by column."""
    board = load_board_or_die(args.repo, args.json)

    columns = []
    for col in board.columns:
        if args.column and col.order != args.column:
            continue
        col_name = first_title(col.sections)
        cards = []
        for card_id in col.links or []:
            card = board.cards[card_id]
            title = first_title(card.sections) if card else card_id
            cards.append({"id": card_id, "title": title})
        columns.append({"id": col.order, "name": col_name, "cards": cards})

    if args.json:
        items = [
            {"id": c["id"], "title": c["title"], "column": {"id": col["id"], "name": col["name"]}}
            for col in columns
            for c in col["cards"]
        ]
        output_json(items)
    else:
        for col in columns:
            print(f"{col['id']}  {col['name']}")
            for c in col["cards"]:
                print(f"  {c['id']}  {c['title']}")

    return 0


def card_get(args) -> int:
    """Dump card markdown content."""
    args.id = normalize_id(args.id)
    board = load_board_or_die(args.repo, args.json)
    card = find_card(board, args.id, args.json)

    markdown = sections_to_text(card.sections, card.meta)

    if args.json:
        col = find_card_column(board, args.id)
        data = {
            "id": args.id,
            "title": first_title(card.sections),
            "meta": meta_to_dict(card.meta),
            "markdown": markdown,
        }
        if col:
            data["column"] = {"id": col.order, "name": first_title(col.sections)}
        output_json(data)
    else:
        sys.stdout.write(markdown)

    return 0


def card_set(args) -> int:
    """Write card markdown from stdin."""
    args.id = normalize_id(args.id)
    board = load_board_or_die(args.repo, args.json)
    card = find_card(board, args.id, args.json)

    text = sys.stdin.read()
    new_sections, new_meta = markdown_to_sections(text)

    card.sections = new_sections
    card.meta = new_meta

    title = first_title(new_sections)
    commit = save(board, f"Update card {args.id}: {title}")

    output_result(
        {"id": args.id, "commit": commit},
        f"Updated card {args.id} ({commit[:7]})",
        args.json,
    )

    return 0


def card_add(args) -> int:
    """Create a new card."""
    board = load_board_or_die(args.repo, args.json)

    column = None
    if args.column:
        column = find_column(board, args.column, args.json)

    card_id, card = create_card(board, args.title, args.body, column=column)

    col = find_card_column(board, card_id)
    col_name = first_title(col.sections) if col else "none"

    commit = save(board, f"Add card: {args.title}")

    data = {"id": card_id, "title": args.title, "commit": commit}
    if col:
        data["column"] = {"id": col.order, "name": col_name}

    output_result(data, f"Created card {card_id} in {col_name} ({commit[:7]})", args.json)

    return 0


def card_move(args) -> int:
    """Move a card to a column."""
    args.id = normalize_id(args.id)
    board = load_board_or_die(args.repo, args.json)
    find_card(board, args.id, args.json)
    target = find_column(board, args.column, args.json)

    position = args.position - 1 if args.position is not None else None
    move_card(board, args.id, target, position=position)

    col_name = first_title(target.sections)
    commit = save(board, f"Move card {args.id} to {col_name}")

    output_result(
        {
            "id": args.id,
            "column": {"id": target.order, "name": col_name},
            "commit": commit,
        },
        f"Moved card {args.id} to {col_name} ({commit[:7]})",
        args.json,
    )

    return 0


def card_archive(args) -> int:
    """Archive a card."""
    args.id = normalize_id(args.id)
    board = load_board_or_die(args.repo, args.json)
    find_card(board, args.id, args.json)

    archive_card(board, args.id)

    commit = save(board, f"Archive card {args.id}")

    output_result(
        {"id": args.id, "commit": commit},
        f"Archived card {args.id} ({commit[:7]})",
        args.json,
    )

    return 0
