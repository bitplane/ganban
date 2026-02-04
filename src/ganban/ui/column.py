"""Column widgets for ganban UI."""

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.geometry import Offset
from textual.message import Message
from textual.widgets import Static

from ganban.models import Board, Column
from ganban.writer import build_column_path, create_column
from ganban.ui.card import AddCardWidget, CardWidget
from ganban.ui.drag import DraggableMixin, DragStart
from ganban.ui.widgets import EditableLabel


class ColumnPlaceholder(Static):
    """Placeholder showing where a dragged column will drop."""

    DEFAULT_CSS = """
    ColumnPlaceholder {
        width: 1fr;
        min-width: 20;
        max-width: 25;
        height: 100%;
        border: dashed $primary;
        background: $surface-darken-1;
    }
    """


class ColumnHeader(DraggableMixin, Static):
    """Draggable column header."""

    DEFAULT_CSS = """
    ColumnHeader {
        width: 100%;
        height: auto;
    }
    ColumnHeader > Static {
        width: 100%;
        text-align: center;
        text-style: bold;
    }
    """

    HORIZONTAL_ONLY = True

    def __init__(self, column_name: str):
        Static.__init__(self)
        self._init_draggable()
        self.column_name = column_name

    def compose(self) -> ComposeResult:
        yield EditableLabel(self.column_name, click_to_edit=True)

    def draggable_drag_started(self, mouse_pos: Offset) -> None:
        self.post_message(DragStart(self, mouse_pos))

    def draggable_clicked(self) -> None:
        self.query_one(EditableLabel).start_editing()


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
    ColumnWidget.dragging {
        layer: overlay;
        border: solid $primary;
        opacity: 0.8;
    }
    .column-body {
        width: 100%;
        height: 1fr;
    }
    """

    class DragStart(Message):
        """Posted when a column drag begins."""

        def __init__(self, column_widget: "ColumnWidget", mouse_offset: Offset) -> None:
            super().__init__()
            self.column_widget = column_widget
            self.mouse_offset = mouse_offset

        @property
        def control(self) -> "ColumnWidget":
            """The column widget being dragged."""
            return self.column_widget

    def __init__(self, column: Column, board: Board):
        super().__init__()
        self.column = column
        self.board = board

    def compose(self) -> ComposeResult:
        yield ColumnHeader(self.column.name)
        with VerticalScroll(classes="column-body"):
            for link in self.column.links:
                card = self.board.cards.get(link.card_id)
                title = card.content.title if card else link.slug
                yield CardWidget(link, title, self.board)
            yield AddCardWidget(self.column, self.board)

    def on_drag_start(self, event: DragStart) -> None:
        """Convert header DragStart to ColumnWidget.DragStart."""
        if isinstance(event.widget, ColumnHeader):
            event.stop()
            self.post_message(self.DragStart(self, event.mouse_offset))

    def on_editable_label_changed(self, event: EditableLabel.Changed) -> None:
        """Update column name when header is edited."""
        event.stop()
        if event.new_value:
            self.column.name = event.new_value
            self.column.path = build_column_path(self.column.order, event.new_value, self.column.hidden)


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
        yield EditableLabel("+", classes="column-header")

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
