"""Detail modals for viewing and editing markdown content."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.events import Click
from textual.screen import ModalScreen

from ganban.models import Board, Card, Column
from ganban.ui.edit import MarkdownDocEditor


class DetailModal(ModalScreen[None]):
    """Base modal screen for detail editing."""

    DEFAULT_CSS = """
    DetailModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.6);
    }

    #detail-container {
        width: 80%;
        height: 80%;
        background: $surface;
        border: solid $primary;
        padding: 1 1;
    }
    """

    BINDINGS = [
        ("escape", "close", "Close"),
        ("ctrl+q", "quit", "Quit"),
    ]

    def on_click(self, event: Click) -> None:
        """Dismiss modal when clicking outside the detail container."""
        container = self.query_one("#detail-container")
        if not container.region.contains(event.screen_x, event.screen_y):
            self.dismiss()

    def action_close(self) -> None:
        """Close the modal."""
        self.dismiss()

    def action_quit(self) -> None:
        """Quit the app."""
        self.app.exit()


class CardDetailModal(DetailModal):
    """Modal screen showing full card details."""

    def __init__(self, card: Card) -> None:
        super().__init__()
        self.card = card

    def compose(self) -> ComposeResult:
        with Vertical(id="detail-container"):
            yield MarkdownDocEditor(self.card.content)


class ColumnDetailModal(DetailModal):
    """Modal screen showing full column details."""

    def __init__(self, column: Column) -> None:
        super().__init__()
        self.column = column

    def compose(self) -> ComposeResult:
        with Vertical(id="detail-container"):
            yield MarkdownDocEditor(self.column.content)


class BoardDetailModal(DetailModal):
    """Modal screen showing full board details."""

    def __init__(self, board: Board) -> None:
        super().__init__()
        self.board = board

    def compose(self) -> ComposeResult:
        with Vertical(id="detail-container"):
            yield MarkdownDocEditor(self.board.content)
