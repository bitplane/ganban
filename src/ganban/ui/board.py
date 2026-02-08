"""Board screen showing kanban columns and cards."""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Static

from ganban.model.card import archive_card, move_card
from ganban.model.column import archive_column, move_column
from ganban.model.node import Node
from ganban.model.writer import save_board
from ganban.parser import first_title
from ganban.ui.card import AddCard, CardWidget
from ganban.ui.column import AddColumn, ColumnWidget
from ganban.ui.constants import ICON_BOARD, ICON_EDIT
from ganban.ui.detail import BoardDetailModal
from ganban.ui.drag import DragStarted
from ganban.ui.drag_managers import CardDragManager, ColumnDragManager
from ganban.ui.edit import EditableText, TextEditor
from ganban.ui.menu import ContextMenu, MenuItem, MenuSeparator
from ganban.ui.watcher import NodeWatcherMixin


class BoardScreen(NodeWatcherMixin, Screen):
    """Main board screen showing all columns."""

    BINDINGS = [
        Binding("escape", "cancel_drag", "Cancel drag", show=False),
        ("ctrl+s", "save", "Save"),
        ("ctrl+@", "context_menu", "Context menu"),
    ]

    DEFAULT_CSS = """
    BoardScreen {
        width: 100%;
        height: 100%;
        layout: vertical;
        layers: base overlay;
    }
    #board-header {
        width: 100%;
        height: auto;
        background: $primary;
    }
    #columns {
        width: 100%;
        height: 1fr;
        overflow: auto;
    }
    """

    def __init__(self, board: Node):
        self._init_watcher()
        super().__init__()
        self.board = board
        self._card_drag = CardDragManager(self)
        self._column_drag = ColumnDragManager(self)

    def compose(self) -> ComposeResult:
        title = first_title(self.board.sections)
        yield EditableText(title, Static(title), TextEditor(), id="board-header")

        visible_columns = [c for c in self.board.columns if not c.hidden]

        with Horizontal(id="columns"):
            for column in visible_columns:
                yield ColumnWidget(column, self.board)
            yield AddColumn(self.board)

        yield Footer()

    def on_mount(self) -> None:
        self.node_watch(self.board, "sections", self._on_board_sections_changed)
        self.call_after_refresh(self._focus_first_card)

    def _focus_first_card(self) -> None:
        columns = list(self.query(ColumnWidget))
        for col in columns:
            focusable = [c for c in col.children if c.can_focus]
            if focusable:
                focusable[0].focus()
                return

    def _on_board_sections_changed(self, node, key, old, new) -> None:
        """Update board header when title changes."""
        keys = self.board.sections.keys()
        if not keys:
            return  # transient empty state during rename_first_key rebuild
        new_title = keys[0]
        header = self.query_one("#board-header", EditableText)
        if header.value != new_title:
            header.value = new_title

    def on_drag_started(self, event: DragStarted) -> None:
        """Handle drag start from a card."""
        if isinstance(event.widget, CardWidget):
            event.stop()
            self._card_drag.start(event.widget, event.mouse_offset)

    def on_column_widget_drag_started(self, event: ColumnWidget.DragStarted) -> None:
        """Handle the start of a column drag."""
        event.stop()
        self._column_drag.start(event.column_widget, event.mouse_offset)

    def on_mouse_move(self, event) -> None:
        """Update drag overlay position."""
        if self._column_drag.active:
            self._column_drag.update_position(event.screen_x, event.screen_y)
        elif self._card_drag.active:
            self._card_drag.update_position(event.screen_x, event.screen_y)

    def on_mouse_up(self, event) -> None:
        """Complete the drag operation."""
        if self._column_drag.active:
            self._column_drag.finish()
        elif self._card_drag.active:
            self._card_drag.finish()

    def action_cancel_drag(self) -> None:
        """Cancel the current drag operation."""
        if self._column_drag.active:
            self._column_drag.cancel()
        elif self._card_drag.active:
            self._card_drag.cancel()

    def on_editable_text_changed(self, event: EditableText.Changed) -> None:
        """Update board title when header is edited."""
        header = self.query_one("#board-header", EditableText)
        if event.control is header:
            event.stop()
            self.board.sections.rename_first_key(event.new_value)

    def on_click(self, event) -> None:
        """Show context menu on right-click on board header."""
        if event.button != 3:
            return
        header = self.query_one("#board-header", EditableText)
        if header.region.contains(event.screen_x, event.screen_y):
            event.stop()
            self.show_context_menu(event.screen_x, event.screen_y)

    def show_context_menu(self, x: int | None = None, y: int | None = None) -> None:
        if x is None or y is None:
            region = self.query_one("#board-header", EditableText).region
            x = region.x + region.width // 2
            y = region.y + region.height // 2
        title = first_title(self.board.sections)
        items = [
            MenuItem(f"{ICON_BOARD} {title}", disabled=True),
            MenuSeparator(),
            MenuItem(f"{ICON_EDIT} Edit", "edit"),
        ]
        self.app.push_screen(ContextMenu(items, x, y), self._on_header_menu_closed)

    def _on_header_menu_closed(self, item: MenuItem | None) -> None:
        """Handle board header context menu selection."""
        if item and item.item_id == "edit":
            self.app.push_screen(BoardDetailModal(self.board))

    def action_context_menu(self) -> None:
        """Show context menu for the focused widget."""
        focused = self.focused
        if focused is None:
            return
        region = focused.region
        x = region.x + region.width // 2
        y = region.y + region.height // 2
        widget = focused
        while widget is not None:
            if hasattr(widget, "show_context_menu"):
                widget.show_context_menu(x, y)
                return
            widget = widget.parent

    def action_save(self) -> None:
        """Save the board to git."""
        new_commit = save_board(self.board)
        self.board.commit = new_commit
        self.notify("Saved")

    def on_card_widget_move_requested(self, event: CardWidget.MoveRequested) -> None:
        """Handle card move request."""
        event.stop()
        card = event.card
        col_name = event.target_column

        target_col = next((c for c in self.board.columns if first_title(c.sections) == col_name), None)
        if not target_col:
            return

        move_card(self.board, card.card_id, target_col)

    def on_card_widget_archive_requested(self, event: CardWidget.ArchiveRequested) -> None:
        """Handle card archive request."""
        event.stop()
        archive_card(self.board, event.card.card_id)

    def on_add_card_card_created(self, event: AddCard.CardCreated) -> None:
        """Handle new card creation — model already updated by create_card."""
        event.stop()

    def on_add_column_column_created(self, event: AddColumn.ColumnCreated) -> None:
        """Handle new column creation."""
        event.stop()
        columns_container = self.query_one("#columns", Horizontal)
        add_widget = columns_container.query_one(AddColumn)
        new_widget = ColumnWidget(event.column, self.board)
        columns_container.mount(new_widget, before=add_widget)

    def _move_column_to_index(self, col_widget: ColumnWidget, new_index: int) -> None:
        """Move column to new position in both model and UI."""
        move_column(self.board, col_widget.column, new_index)
        self._sync_column_order()

    def _sync_column_order(self) -> None:
        """Reorder column widgets to match model order."""
        columns_container = self.query_one("#columns", Horizontal)
        add_column = columns_container.query_one(AddColumn)
        widgets_by_column = {id(cw.column): cw for cw in self.query(ColumnWidget)}

        insert_before = add_column
        for column in reversed(list(self.board.columns)):
            if id(column) not in widgets_by_column:
                continue  # skip hidden columns
            widget = widgets_by_column[id(column)]
            columns_container.move_child(widget, before=insert_before)
            insert_before = widget

    def on_column_widget_move_requested(self, event: ColumnWidget.MoveRequested) -> None:
        """Handle column move request."""
        event.stop()
        col_widget = event.column_widget
        direction = event.direction

        all_cols = list(self.board.columns)
        current_index = next(i for i, c in enumerate(all_cols) if c is col_widget.column)
        new_index = current_index + direction

        if new_index < 0 or new_index >= len(all_cols):
            return

        self._move_column_to_index(col_widget, new_index)

    def on_column_widget_archive_requested(self, event: ColumnWidget.ArchiveRequested) -> None:
        """Handle column archive request."""
        event.stop()
        col_widget = event.column_widget
        archive_column(self.board, col_widget.column.order)
        col_widget.remove()
