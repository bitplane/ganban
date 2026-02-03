"""Entry point for ganban CLI."""

import argparse
from pathlib import Path

from ganban.ui import GanbanApp


def main():
    parser = argparse.ArgumentParser(description="Git-based kanban board TUI")
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to git repository (default: current directory)",
    )
    args = parser.parse_args()

    repo_path = Path(args.path).resolve()
    app = GanbanApp(repo_path)
    app.run()


if __name__ == "__main__":
    main()
