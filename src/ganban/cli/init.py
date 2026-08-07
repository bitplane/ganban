"""Handler for 'ganban init'."""

from pathlib import Path

from ganban.cli._common import load_board_or_die, output_json, save
from ganban.git import has_branch_sync, init_repo, is_git_repo
from ganban.model.board import create_default_board
from ganban.parser import first_title


def init_board(args) -> int:
    """Initialize a ganban board in the repository."""
    repo_path = Path(args.repo).resolve()

    if not is_git_repo(repo_path):
        init_repo(repo_path)

    if has_branch_sync(repo_path):
        board = load_board_or_die(str(repo_path), args.json)
        columns = [first_title(c.sections) for c in board.columns]
        if args.json:
            output_json({"repo_path": str(repo_path), "columns": columns, "created": False})
        else:
            print(f"Board already initialized at {repo_path}")
        return 0

    board = create_default_board(repo_path)
    save(board, "Initialize ganban board")

    columns = [first_title(c.sections) for c in board.columns]
    if args.json:
        output_json({"repo_path": str(repo_path), "columns": columns, "created": True})
    else:
        print(f"Initialized ganban board at {repo_path}")
        print(f"Columns: {', '.join(columns)}")

    return 0
