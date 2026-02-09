"""Handler for 'ganban init'."""

from pathlib import Path

from ganban.cli._common import output_json, save
from ganban.git import init_repo, is_git_repo
from ganban.model.column import create_column
from ganban.model.loader import load_board
from ganban.model.node import BRANCH_NAME, ListNode, Node
from ganban.parser import first_title


def _has_branch(repo_path: Path) -> bool:
    """Synchronous check for ganban branch."""
    from git import Repo

    repo = Repo(repo_path)
    return BRANCH_NAME in [h.name for h in repo.heads]


def init_board(args) -> int:
    """Initialize a ganban board in the repository."""
    repo_path = Path(args.repo).resolve()

    if not is_git_repo(repo_path):
        init_repo(repo_path)

    if _has_branch(repo_path):
        board = load_board(str(repo_path))
        columns = [first_title(c.sections) for c in board.columns]
        if args.json:
            output_json({"repo_path": str(repo_path), "columns": columns, "created": False})
        else:
            print(f"Board already initialized at {repo_path}")
        return 0

    board = Node(repo_path=str(repo_path))
    board.sections = ListNode()
    board.sections["ganban"] = ""
    board.meta = {}
    board.cards = ListNode()
    board.columns = ListNode()
    backlog = create_column(board, "Backlog", order="1")
    backlog.meta.compact = True
    create_column(board, "Doing", order="2")
    create_column(board, "Done", order="3")
    save(board, "Initialize ganban board")

    columns = [first_title(c.sections) for c in board.columns]
    if args.json:
        output_json({"repo_path": str(repo_path), "columns": columns, "created": True})
    else:
        print(f"Initialized ganban board at {repo_path}")
        print(f"Columns: {', '.join(columns)}")

    return 0
