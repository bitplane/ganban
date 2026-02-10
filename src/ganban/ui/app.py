"""Main Textual application for ganban."""

from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from ganban.git import has_branch, init_repo, is_git_repo
from ganban.model.loader import load_board
from ganban.model.node import ListNode, Node
from ganban.model.column import create_column
from ganban.model.writer import save_board
from ganban.ui.board import BoardScreen


class ConfirmInitScreen(ModalScreen[bool]):
    """Modal screen asking to initialize a git repo."""

    CSS = """
    ConfirmInitScreen {
        align: center middle;
    }
    #dialog {
        width: 70;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    #message {
        text-align: center;
        margin-bottom: 1;
    }
    #buttons {
        width: 100%;
        height: 3;
        align: center middle;
    }
    Button {
        margin: 0 2;
    }
    """

    def __init__(self, path: Path):
        super().__init__()
        self.path = path

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static(f"{self.path} is not a git repository. Create one?", id="message")
            with Horizontal(id="buttons"):
                yield Button("Yes", id="yes", variant="primary")
                yield Button("No", id="no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")


class GanbanApp(App):
    """Git-based kanban board TUI."""

    CSS = """
    Tooltip {
        padding: 0 1;
        margin: 0;
    }
    """

    TITLE = "ganban"
    BINDINGS = [("ctrl+q", "quit", "Quit")]

    def __init__(self, repo_path: Path):
        super().__init__()
        self.repo_path = repo_path
        self.board: Node | None = None

    async def on_mount(self) -> None:
        if not is_git_repo(self.repo_path):
            self.push_screen(ConfirmInitScreen(self.repo_path), self._on_init_response)
        else:
            await self._load_board()

    async def _on_init_response(self, result: bool) -> None:
        if result:
            init_repo(self.repo_path)
            await self._load_board()
        else:
            self.exit()

    async def _load_board(self) -> None:
        """Load or create the board and show it."""
        if not await has_branch(self.repo_path):
            board = Node(repo_path=str(self.repo_path))
            board.sections = ListNode()
            board.sections["ganban"] = ""
            board.meta = {}
            board.cards = ListNode()
            board.columns = ListNode()
            create_column(board, "Backlog", order="1")
            create_column(board, "Doing", order="2")
            create_column(board, "Done", order="3")
            save_board(board, message="Initialize ganban board")

        self.board = load_board(str(self.repo_path))
        self.push_screen(BoardScreen(self.board))

    def action_quit(self) -> None:
        """Cancel sync, save and quit."""
        screen = self.screen
        if hasattr(screen, "_sync_task") and screen._sync_task is not None:
            screen._sync_task.cancel()
        if self.board:
            save_board(self.board)
        self.exit()
