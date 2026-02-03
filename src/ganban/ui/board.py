"""Board screen showing kanban columns and tickets."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Static

from ganban.models import Board, Column, TicketLink
from ganban.writer import create_column
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
        max-width: 25;
        padding: 0 1;
        border-right: tall $surface-lighten-1;
    }
    .column-header {
        width: 100%;
        height: auto;
    }
    .column-header > Static {
        width: 100%;
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
        yield EditableLabel(self.column.name, classes="column-header")
        with VerticalScroll(classes="column-body"):
            for link in self.column.links:
                ticket = self.board.tickets.get(link.ticket_id)
                title = ticket.content.title if ticket else link.slug
                yield TicketCard(link, title)


class AddColumnWidget(Vertical):
    """Widget to add a new column."""

    DEFAULT_CSS = """
    AddColumnWidget {
        width: 1fr;
        height: 100%;
        min-width: 20;
        max-width: 25;
        padding: 0 1;
    }
    AddColumnWidget .column-header > Static {
        text-align: center;
        text-style: bold;
    }
    """

    def __init__(self, board: Board):
        super().__init__()
        self.board = board

    def compose(self) -> ComposeResult:
        yield EditableLabel("+", click_to_edit=False, classes="column-header")

    def on_click(self) -> None:
        self.query_one(EditableLabel).start_editing(text="")

    def on_editable_label_changed(self, event: EditableLabel.Changed) -> None:
        event.stop()
        if event.new_value and event.new_value != "+":
            new_column = create_column(self.board, event.new_value)
            new_widget = ColumnWidget(new_column, self.board)
            self.parent.mount(new_widget, before=self)
        label = self.query_one(EditableLabel)
        label.value = "+"


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
        height: auto;
        background: $primary;
    }
    #board-header > Static {
        width: 100%;
        text-align: center;
        text-style: bold;
    }
    #columns {
        width: 100%;
        height: 1fr;
        overflow-x: auto;
    }
    """

    def __init__(self, board: Board):
        super().__init__()
        self.board = board

    def compose(self) -> ComposeResult:
        title = self.board.content.title or "ganban"
        yield EditableLabel(title, id="board-header")

        visible_columns = [c for c in self.board.columns if not c.hidden]

        with Horizontal(id="columns"):
            for column in visible_columns:
                yield ColumnWidget(column, self.board)
            yield AddColumnWidget(self.board)
