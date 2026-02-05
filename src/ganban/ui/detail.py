"""Detail modals for viewing and editing markdown content."""

from datetime import date

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Click
from textual.screen import ModalScreen

from ganban.models import Board, Card, Column
from ganban.ui.color import ColorButton
from ganban.ui.due import DueDateWidget
from ganban.ui.edit import DocHeader, MarkdownDocEditor


class DetailModal(ModalScreen[None]):
    """Base modal screen for detail editing."""

    DEFAULT_CSS = """
    DetailModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.6);
    }

    #detail-container {
        width: 90%;
        height: 90%;
        background: $surface;
        border: solid $primary;
        padding: 0 1;
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

    DEFAULT_CSS = """
    CardDetailModal #card-metadata {
        width: 100%;
        height: 1;
    }
    """

    def __init__(self, card: Card) -> None:
        super().__init__()
        self.card = card

    def compose(self) -> ComposeResult:
        due = self._get_due_date()
        with Vertical(id="detail-container"):
            yield DocHeader(self.card.content)
            with Horizontal(id="card-metadata"):
                yield DueDateWidget(due=due)
            yield MarkdownDocEditor(self.card.content, include_header=False)

    def _get_due_date(self) -> date | None:
        due_str = self.card.content.meta.get("due")
        if due_str:
            return date.fromisoformat(due_str)
        return None

    def on_due_date_widget_changed(self, event: DueDateWidget.Changed) -> None:
        event.stop()
        if event.due:
            self.card.content.meta["due"] = event.due.isoformat()
        else:
            self.card.content.meta.pop("due", None)


class ColumnDetailModal(DetailModal):
    """Modal screen showing full column details."""

    DEFAULT_CSS = """
    ColumnDetailModal #column-metadata {
        width: 100%;
        height: 1;
    }
    """

    def __init__(self, column: Column) -> None:
        super().__init__()
        self.column = column

    def compose(self) -> ComposeResult:
        color = self.column.content.meta.get("color")
        with Vertical(id="detail-container"):
            yield DocHeader(self.column.content)
            with Horizontal(id="column-metadata"):
                yield ColorButton(color=color)
            yield MarkdownDocEditor(self.column.content, include_header=False)

    def on_color_button_color_selected(self, event: ColorButton.ColorSelected) -> None:
        event.stop()
        if event.color:
            self.column.content.meta["color"] = event.color
        else:
            self.column.content.meta.pop("color", None)


class BoardDetailModal(DetailModal):
    """Modal screen showing full board details."""

    def __init__(self, board: Board) -> None:
        super().__init__()
        self.board = board

    def compose(self) -> ComposeResult:
        with Vertical(id="detail-container"):
            yield MarkdownDocEditor(self.board.content)
