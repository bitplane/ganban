"""Card widgets for ganban UI."""

from textual.app import ComposeResult
from textual.geometry import Offset
from textual.widgets import Static

from ganban.models import Board, CardLink, Column
from ganban.writer import create_card
from ganban.ui.drag import DraggableMixin, DragStart
from ganban.ui.widgets import EditableLabel


class CardWidget(DraggableMixin, Static):
    """A single card in a column."""

    DEFAULT_CSS = """
    CardWidget {
        width: 100%;
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
        border: solid $primary-lighten-2;
        background: $surface;
    }
    CardWidget:hover {
        border: solid $primary;
    }
    CardWidget.dragging {
        display: none;
    }
    """

    def __init__(self, link: CardLink, title: str, board: Board):
        Static.__init__(self)
        self._init_draggable()
        self.link = link
        self.title = title
        self.board = board

    def compose(self) -> ComposeResult:
        yield EditableLabel(self.title or self.link.slug)

    def draggable_drag_started(self, mouse_pos: Offset) -> None:
        self.post_message(DragStart(self, mouse_pos))

    def draggable_clicked(self) -> None:
        self.query_one(EditableLabel).start_editing()

    def on_editable_label_changed(self, event: EditableLabel.Changed) -> None:
        """Update card title when edited."""
        event.stop()
        card = self.board.cards.get(self.link.card_id)
        if card and event.new_value:
            card.content.title = event.new_value
            self.title = event.new_value


class AddCardWidget(Static):
    """Widget to add a new card to a column."""

    DEFAULT_CSS = """
    AddCardWidget {
        width: 100%;
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
        border: dashed $surface-lighten-2;
    }
    AddCardWidget > EditableLabel > Static {
        text-align: center;
        color: $text-muted;
    }
    """

    def __init__(self, column: Column, board: Board):
        super().__init__()
        self.column = column
        self.board = board

    def compose(self) -> ComposeResult:
        yield EditableLabel("+")

    def on_click(self) -> None:
        self.query_one(EditableLabel).start_editing(text="")

    def on_editable_label_changed(self, event: EditableLabel.Changed) -> None:
        event.stop()
        if event.new_value and event.new_value != "+":
            new_card = create_card(self.board, event.new_value, column=self.column)
            link = self.column.links[-1]  # create_card adds link to end
            card_widget = CardWidget(link, new_card.content.title, self.board)
            self.parent.mount(card_widget, before=self)
        self.query_one(EditableLabel).value = "+"
