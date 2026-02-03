"""Board screen showing kanban columns and tickets."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Static

from ganban.models import Board, Column, TicketLink
from ganban.ui.widgets import EditableLabel


class TicketCard(Static):
    """A single ticket card in a column."""

    DEFAULT_CSS = """
    TicketCard {
        width: 100%;
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
        border: solid $primary-lighten-2;
        background: $surface;
    }
    TicketCard:hover {
        border: solid $primary;
    }
    """

    def __init__(self, link: TicketLink, title: str):
        super().__init__()
        self.link = link
        self.title = title

    def compose(self) -> ComposeResult:
        yield EditableLabel(self.title or self.link.slug)


class ColumnWidget(Vertical):
    """A single column on the board."""

    DEFAULT_CSS = """
    ColumnWidget {
        width: 1fr;
        height: 100%;
        min-width: 20;
        padding: 0 1;
        border-right: tall $surface-lighten-1;
    }
    ColumnWidget:last-of-type {
        border-right: none;
    }
    .column-header {
        width: 100%;
        height: 1;
        text-align: center;
        text-style: bold;
    }
    .column-body {
        width: 100%;
        height: 1fr;
    }
    """

    def __init__(self, column: Column, board: Board):
        super().__init__()
        self.column = column
        self.board = board

    def compose(self) -> ComposeResult:
        yield Static(self.column.name, classes="column-header")
        with VerticalScroll(classes="column-body"):
            for link in self.column.links:
                ticket = self.board.tickets.get(link.ticket_id)
                title = ticket.content.title if ticket else link.slug
                yield TicketCard(link, title)


class BoardScreen(Screen):
    """Main board screen showing all columns."""

    DEFAULT_CSS = """
    BoardScreen {
        width: 100%;
        height: 100%;
        layout: vertical;
    }
    #board-header {
        width: 100%;
        height: 1;
        background: $primary;
        text-align: center;
        text-style: bold;
    }
    #columns {
        width: 100%;
        height: 1fr;
    }
    #empty-message {
        width: 100%;
        height: 1fr;
        align: center middle;
        text-align: center;
    }
    """

    def __init__(self, board: Board):
        super().__init__()
        self.board = board

    def compose(self) -> ComposeResult:
        title = self.board.content.title or "ganban"
        yield Static(title, id="board-header")

        visible_columns = [c for c in self.board.columns if not c.hidden]

        if visible_columns:
            with Horizontal(id="columns"):
                for column in visible_columns:
                    yield ColumnWidget(column, self.board)
        else:
            yield Static("No columns yet. Press 'c' to create a column.", id="empty-message")
