"""Entry point for ganban CLI."""

import sys
from pathlib import Path

NOUNS = {"init", "board", "card", "column", "sync", "web", "serve"}


def main():
    # No subcommand or non-noun argument = TUI mode
    if len(sys.argv) < 2 or (sys.argv[1] not in NOUNS and not sys.argv[1].startswith("-")):
        from ganban.ui import GanbanApp

        path = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "."
        app = GanbanApp(Path(path).resolve())
        app.run()
        return

    # Global --help before noun
    if sys.argv[1] in ("-h", "--help"):
        from ganban.cli import build_parser

        build_parser().parse_args()
        return

    from ganban.cli import build_parser

    parser = build_parser()
    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
