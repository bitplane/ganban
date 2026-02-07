"""Column widgets for ganban UI."""

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.geometry import Offset
from textual.message import Message
from textual.color import Color
from textual.widgets import Rule, Static

from ganban.model.node import Node
from ganban.model.writer import build_column_path, create_column
from ganban.parser import first_title
from ganban.ui.card import AddCard, CardWidget
from ganban.ui.color import build_color_menu
from ganban.ui.constants import ICON_PALETTE
from ganban.ui.detail import ColumnDetailModal
from ganban.ui.drag import DraggableMixin
from ganban.ui.edit.document import _rename_first_key
from ganban.ui.menu import ContextMenu, MenuItem, MenuSeparator
from ganban.ui.edit import EditableText, TextEditor


class ColumnWidget(DraggableMixin, Vertical):
    """A single column on the board."""

    DEFAULT_CSS = """
    ColumnWidget {
        width: 1fr;
        height: 100%;
        min-width: 25;
        max-width: 25;
        padding: 0 1;
        border-right: tall $surface-lighten-1;
    }
    ColumnWidget.dragging {
        layer: overlay;
        border: solid $primary;
        opacity: 0.8;
    }
    ColumnWidget > EditableText > ContentSwitcher > Static {
        width: 100%;
        text-align: center;
        text-style: bold;
    }
    ColumnWidget > Rule.-horizontal {
        margin: 0;
    }
    .column-body {
        width: 100%;
        height: 1fr;
    }
    """

    HORIZONTAL_ONLY = True

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

    def __init__(self, column: Node, board: Node):
        Vertical.__init__(self)
        self._init_draggable()
        self.column = column
        self.board = board

    def compose(self) -> ComposeResult:
        name = first_title(self.column.sections)
        yield EditableText(name, Static(name), TextEditor(), id="column-title")
        yield Rule()
        with VerticalScroll(classes="column-body"):
            for card_id in self.column.links:
                yield CardWidget(card_id, self.board)
            yield AddCard(self.column, self.board)

    def draggable_drag_started(self, mouse_pos: Offset) -> None:
        self.post_message(self.DragStarted(self, mouse_pos))

    def draggable_clicked(self) -> None:
        pass  # Click without drag - no action needed

    def on_editable_text_changed(self, event: EditableText.Changed) -> None:
        """Update column name when header is edited."""
        event.stop()
        if event.new_value:
            _rename_first_key(self.column.sections, event.new_value)
            self.column.dir_path = build_column_path(self.column.order, event.new_value, self.column.hidden)

    def on_click(self, event) -> None:
        """Show context menu on right-click."""
        if event.button == 3:
            event.stop()
            col_index = self._get_column_index()
            visible_count = sum(1 for c in self.board.columns if not c.hidden)

            items = [
                MenuItem("Edit", "edit"),
                MenuItem(f"{ICON_PALETTE} Color", "color", submenu=build_color_menu()),
                MenuSeparator(),
                MenuItem("Move Left", "move_left", disabled=(col_index == 0)),
                MenuItem("Move Right", "move_right", disabled=(col_index >= visible_count - 1)),
                MenuSeparator(),
                MenuItem("Delete", "delete"),
            ]

            menu = ContextMenu(items, event.screen_x, event.screen_y)
            self.app.push_screen(menu, self._on_menu_closed)

    def on_mount(self) -> None:
        self._apply_color()
        self._unwatch_sections = self.column.watch("sections", self._on_sections_changed)
        self._unwatch_meta = self.column.watch("meta", self._on_meta_changed)

    def _on_meta_changed(self, node, key, old, new) -> None:
        """Re-apply color when meta changes."""
        self._apply_color()

    def _on_sections_changed(self, node, key, old, new) -> None:
        """Sync column dir_path and UI when sections title changes."""
        keys = self.column.sections.keys()
        if not keys:
            return  # transient empty state during _rename_first_key rebuild
        new_name = keys[0]
        self.column.dir_path = build_column_path(self.column.order, new_name, self.column.hidden)
        title_widget = self.query_one("#column-title", EditableText)
        if title_widget.value != new_name:
            title_widget.value = new_name

    def _set_color(self, color: str | None) -> None:
        """Update model and re-apply background."""
        self.column.meta.color = color
        self._apply_color()

    def _apply_color(self) -> None:
        color_hex = self.column.meta.color
        if color_hex:
            try:
                self.styles.background = Color.parse(color_hex)
            except ValueError:
                self.styles.clear_rule("background")
        else:
            self.styles.clear_rule("background")

    def _on_menu_closed(self, item: MenuItem | None) -> None:
        """Handle context menu selection."""
        if item is None:
            return
        if item.item_id == "none" or item.item_id.startswith("#"):
            self._set_color(None if item.item_id == "none" else item.item_id)
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

        def __init__(self, column: Node):
            super().__init__()
            self.column = column

    DEFAULT_CSS = """
    AddColumn {
        width: 1fr;
        height: 100%;
        min-width: 25;
        max-width: 25;
        padding: 0 1;
    }
    AddColumn .column-header > ContentSwitcher > Static {
        text-align: center;
        text-style: bold;
    }
    """

    def __init__(self, board: Node):
        super().__init__()
        self.board = board

    def compose(self) -> ComposeResult:
        yield EditableText("", Static("+"), TextEditor(), placeholder="+", classes="column-header")

    def on_editable_text_changed(self, event: EditableText.Changed) -> None:
        event.stop()
        if event.new_value:
            new_column = create_column(self.board, event.new_value)
            self.post_message(self.ColumnCreated(new_column))
        self.query_one(EditableText).value = ""
