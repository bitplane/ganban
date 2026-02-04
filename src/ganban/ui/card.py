"""Ticket card widgets for ganban UI."""

from textual.app import ComposeResult
from textual.geometry import Offset
from textual.widgets import Static

from ganban.models import Board, Column, TicketLink
from ganban.writer import create_ticket
from ganban.ui.drag import DraggableMixin, DragStart
from ganban.ui.widgets import EditableLabel


class TicketCard(DraggableMixin, Static):
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
    TicketCard.dragging {
        display: none;
    }
    """

    def __init__(self, link: TicketLink, title: str, board: Board):
        Static.__init__(self)
        self._init_draggable()
        self.link = link
        self.title = title
        self.board = board

    def compose(self) -> ComposeResult:
        yield EditableLabel(self.title or self.link.slug, click_to_edit=False)

    def draggable_drag_started(self, mouse_pos: Offset) -> None:
        self.post_message(DragStart(self, mouse_pos))

    def draggable_clicked(self) -> None:
        self.query_one(EditableLabel).start_editing()

    def on_editable_label_changed(self, event: EditableLabel.Changed) -> None:
        """Update ticket title when edited."""
        event.stop()
        ticket = self.board.tickets.get(self.link.ticket_id)
        if ticket and event.new_value:
            ticket.content.title = event.new_value
            self.title = event.new_value


class AddTicketWidget(Static):
    """Widget to add a new ticket to a column."""

    DEFAULT_CSS = """
    AddTicketWidget {
        width: 100%;
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
        border: dashed $surface-lighten-2;
    }
    AddTicketWidget > EditableLabel > Static {
        text-align: center;
        color: $text-muted;
    }
    """

    def __init__(self, column: Column, board: Board):
        super().__init__()
        self.column = column
        self.board = board

    def compose(self) -> ComposeResult:
        yield EditableLabel("+", click_to_edit=False)

    def on_click(self) -> None:
        self.query_one(EditableLabel).start_editing(text="")

    def on_editable_label_changed(self, event: EditableLabel.Changed) -> None:
        event.stop()
        if event.new_value and event.new_value != "+":
            ticket = create_ticket(self.board, event.new_value, column=self.column)
            link = self.column.links[-1]  # create_ticket adds link to end
            card = TicketCard(link, ticket.content.title, self.board)
            self.parent.mount(card, before=self)
        self.query_one(EditableLabel).value = "+"
