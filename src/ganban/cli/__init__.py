"""CLI argument parser and dispatch for ganban."""

import argparse

from ganban.cli.board import board_get, board_set, board_summary
from ganban.cli.card import card_add, card_archive, card_get, card_list, card_move, card_set
from ganban.cli.column import (
    column_add,
    column_archive,
    column_get,
    column_list,
    column_move,
    column_rename,
    column_set,
)
from ganban.cli.init import init_board
from ganban.cli.sync import sync
from ganban.cli.web import web


def build_parser() -> argparse.ArgumentParser:
    """Build the full CLI argument parser."""
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repo", default=".", help="Path to git repository (default: .)")
    common.add_argument("--json", action="store_true", help="Machine-readable JSON output")

    parser = argparse.ArgumentParser(
        prog="ganban",
        description="Git-based kanban board",
        parents=[common],
    )

    nouns = parser.add_subparsers(dest="noun")

    # --- init ---
    init_p = nouns.add_parser("init", help="Initialize a ganban board", parents=[common])
    init_p.set_defaults(func=init_board)

    # --- board ---
    board_p = nouns.add_parser("board", help="Board operations", parents=[common])
    board_verbs = board_p.add_subparsers(dest="verb")

    board_summary_p = board_verbs.add_parser("summary", help="Show board summary", parents=[common])
    board_summary_p.set_defaults(func=board_summary)

    board_get_p = board_verbs.add_parser("get", help="Dump board index.md", parents=[common])
    board_get_p.set_defaults(func=board_get)

    board_set_p = board_verbs.add_parser("set", help="Write board index.md from stdin", parents=[common])
    board_set_p.set_defaults(func=board_set)

    # board with no verb = summary
    board_p.set_defaults(func=board_summary)

    # --- card ---
    card_p = nouns.add_parser("card", help="Card operations", parents=[common])
    card_verbs = card_p.add_subparsers(dest="verb")

    card_list_p = card_verbs.add_parser("list", help="List cards", parents=[common])
    card_list_p.add_argument("--column", dest="column", help="Filter by column ID")
    card_list_p.set_defaults(func=card_list)

    card_get_p = card_verbs.add_parser("get", help="Dump card markdown", parents=[common])
    card_get_p.add_argument("id", help="Card ID")
    card_get_p.set_defaults(func=card_get)

    card_set_p = card_verbs.add_parser("set", help="Write card markdown from stdin", parents=[common])
    card_set_p.add_argument("id", help="Card ID")
    card_set_p.set_defaults(func=card_set)

    card_add_p = card_verbs.add_parser("add", help="Create a card", parents=[common])
    card_add_p.add_argument("title", help="Card title")
    card_add_p.add_argument("--body", default="", help="Card body text")
    card_add_p.add_argument("--column", dest="column", help="Target column ID")
    card_add_p.set_defaults(func=card_add)

    card_move_p = card_verbs.add_parser("move", help="Move a card", parents=[common])
    card_move_p.add_argument("id", help="Card ID")
    card_move_p.add_argument("--column", dest="column", required=True, help="Target column ID")
    card_move_p.add_argument("--position", type=int, help="Position in column (1-indexed)")
    card_move_p.set_defaults(func=card_move)

    card_archive_p = card_verbs.add_parser("archive", help="Archive a card", parents=[common])
    card_archive_p.add_argument("id", help="Card ID")
    card_archive_p.set_defaults(func=card_archive)

    # card with no verb = list
    card_p.set_defaults(func=card_list, column=None)

    # --- column ---
    col_p = nouns.add_parser("column", help="Column operations", parents=[common])
    col_verbs = col_p.add_subparsers(dest="verb")

    col_list_p = col_verbs.add_parser("list", help="List columns", parents=[common])
    col_list_p.set_defaults(func=column_list)

    col_get_p = col_verbs.add_parser("get", help="Dump column index.md", parents=[common])
    col_get_p.add_argument("id", help="Column ID")
    col_get_p.set_defaults(func=column_get)

    col_set_p = col_verbs.add_parser("set", help="Write column index.md from stdin", parents=[common])
    col_set_p.add_argument("id", help="Column ID")
    col_set_p.set_defaults(func=column_set)

    col_add_p = col_verbs.add_parser("add", help="Create a column", parents=[common])
    col_add_p.add_argument("name", help="Column name")
    col_add_p.add_argument("--hidden", action="store_true", help="Hidden column")
    col_add_p.set_defaults(func=column_add)

    col_move_p = col_verbs.add_parser("move", help="Move a column", parents=[common])
    col_move_p.add_argument("id", help="Column ID")
    col_move_p.add_argument("--position", type=int, required=True, help="New position (1-indexed)")
    col_move_p.set_defaults(func=column_move)

    col_rename_p = col_verbs.add_parser("rename", help="Rename a column", parents=[common])
    col_rename_p.add_argument("id", help="Column ID")
    col_rename_p.add_argument("new_name", help="New column name")
    col_rename_p.set_defaults(func=column_rename)

    col_archive_p = col_verbs.add_parser("archive", help="Archive a column", parents=[common])
    col_archive_p.add_argument("id", help="Column ID")
    col_archive_p.set_defaults(func=column_archive)

    # column with no verb = list
    col_p.set_defaults(func=column_list)

    # --- sync ---
    sync_p = nouns.add_parser("sync", help="Sync board with remotes", parents=[common])
    sync_p.add_argument("-d", "--daemon", action="store_true", help="Run as background daemon")
    sync_p.add_argument("--interval", type=int, default=120, help="Daemon sync interval in seconds (default: 120)")
    sync_p.set_defaults(func=sync)

    # --- web ---
    web_p = nouns.add_parser("web", help="Serve board in browser", parents=[common])
    web_p.add_argument("--host", default="localhost", help="Bind address (default: localhost)")
    web_p.add_argument("--port", type=int, default=8617, help="Port (default: 8617)")
    web_p.set_defaults(func=web)

    return parser
