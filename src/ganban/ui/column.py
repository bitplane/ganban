"""Column widgets for ganban UI."""

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.geometry import Offset
from textual.message import Message
from textual.widgets import Static

from ganban.models import Board, Column
from ganban.writer import build_column_path, create_column
from ganban.ui.detail import ColumnDetailModal
from ganban.ui.drag import DraggableMixin, DragStarted
from ganban.ui.menu import ContextMenu, MenuItem, MenuSeparator
from ganban.ui.edit import EditableText, TextEditor

if TYPE_CHECKING:
    pass


class ColumnHeader(DraggableMixin, Static):
    """Draggable column header."""

    DEFAULT_CSS = """
    ColumnHeader {
        width: 100%;
        height: auto;
    }
    ColumnHeader > EditableText > ContentSwitcher > Static {
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
        yield EditableText(self.column_name, Static(self.column_name), TextEditor())

    def draggable_drag_started(self, mouse_pos: Offset) -> None:
        self.post_message(DragStarted(self, mouse_pos))

    def draggable_clicked(self, click_pos: Offset) -> None:
        self.query_one(EditableText).focus()


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

    class DragStarted(Message):
        """Posted when a column drag begins."""

        def __init__(self, column_widget: "ColumnWidget", mouse_offset: Offset) -> None:
            super().__init__()
            self.column_widget = column_widget
            self.mouse_offset = mouse_offset

        @property
        def control(self) -> "ColumnWidget":
            """The column widget being dragged."""
            return self.column_widget

    class MoveRequested(Message):
        """Posted when column should be moved."""

        def __init__(self, column_widget: "ColumnWidget", direction: int) -> None:
            super().__init__()
            self.column_widget = column_widget
            self.direction = direction  # -1 for left, +1 for right

    class DeleteRequested(Message):
        """Posted when column should be deleted."""

        def __init__(self, column_widget: "ColumnWidget") -> None:
            super().__init__()
            self.column_widget = column_widget

    def __init__(self, column: Column, board: Board):
        super().__init__()
        self.column = column
        self.board = board

    def compose(self) -> ComposeResult:
        from ganban.ui.card import AddCard, CardWidget

        yield ColumnHeader(self.column.name)
        with VerticalScroll(classes="column-body"):
            for link in self.column.links:
                card = self.board.cards.get(link.card_id)
                title = card.content.title if card else link.slug
                yield CardWidget(link, title, self.board)
            yield AddCard(self.column, self.board)

    def on_drag_started(self, event: DragStarted) -> None:
        """Convert header DragStarted to ColumnWidget.DragStarted."""
        if isinstance(event.widget, ColumnHeader):
            event.stop()
            self.post_message(self.DragStarted(self, event.mouse_offset))

    def on_editable_text_changed(self, event: EditableText.Changed) -> None:
        """Update column name when header is edited."""
        event.stop()
        if event.new_value:
            self.column.name = event.new_value
            self.column.path = build_column_path(self.column.order, event.new_value, self.column.hidden)

    def on_click(self, event) -> None:
        """Show context menu on right-click."""
        if event.button == 3:
            event.stop()
            col_index = self._get_column_index()
            visible_count = sum(1 for c in self.board.columns if not c.hidden)

            items = [
                MenuItem("Edit", "edit"),
                MenuSeparator(),
                MenuItem("Move Left", "move_left", disabled=(col_index == 0)),
                MenuItem("Move Right", "move_right", disabled=(col_index >= visible_count - 1)),
                MenuSeparator(),
                MenuItem("Delete", "delete"),
            ]

            menu = ContextMenu(items, event.screen_x, event.screen_y)
            self.app.push_screen(menu, self._on_menu_closed)

    def _on_menu_closed(self, item: MenuItem | None) -> None:
        """Handle context menu selection."""
        if item is None:
            return
        match item.item_id:
            case "edit":
                self.app.push_screen(ColumnDetailModal(self.column))
            case "move_left":
                self.post_message(self.MoveRequested(self, -1))
            case "move_right":
                self.post_message(self.MoveRequested(self, 1))
            case "delete":
                self.post_message(self.DeleteRequested(self))

    def _get_column_index(self) -> int:
        """Get the index of this column among visible columns."""
        visible_columns = [c for c in self.board.columns if not c.hidden]
        for i, col in enumerate(visible_columns):
            if col is self.column:
                return i
        return -1


class AddColumn(Vertical):
    """Widget to add a new column."""

    class ColumnCreated(Message):
        """Posted when a new column is created."""

        def __init__(self, column: Column):
            super().__init__()
            self.column = column

    DEFAULT_CSS = """
    AddColumn {
        width: 1fr;
        height: 100%;
        min-width: 20;
        max-width: 25;
        padding: 0 1;
    }
    AddColumn .column-header > ContentSwitcher > Static {
        text-align: center;
        text-style: bold;
    }
    """

    def __init__(self, board: Board):
        super().__init__()
        self.board = board

    def compose(self) -> ComposeResult:
        yield EditableText("+", Static("+"), TextEditor(), classes="column-header")

    def on_click(self) -> None:
        editable = self.query_one(EditableText)
        editable.value = ""
        editable.focus()

    def on_editable_text_changed(self, event: EditableText.Changed) -> None:
        event.stop()
        if event.new_value and event.new_value != "+":
            new_column = create_column(self.board, event.new_value)
            self.post_message(self.ColumnCreated(new_column))
        editable = self.query_one(EditableText)
        editable.value = "+"
