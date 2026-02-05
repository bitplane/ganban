"""Board screen showing kanban columns and cards."""

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Static

from ganban.models import Board
from ganban.writer import build_column_path, save_board
from ganban.ui.card import AddCard, CardWidget
from ganban.ui.column import AddColumn, ColumnWidget
from ganban.ui.detail import BoardDetailModal
from ganban.ui.drag import DragStarted
from ganban.ui.drag_managers import CardDragManager, ColumnDragManager, renumber_links
from ganban.ui.menu import ContextMenu, MenuItem
from ganban.ui.edit import EditableText, TextEditor


class BoardScreen(Screen):
    """Main board screen showing all columns."""

    BINDINGS = [
        ("escape", "cancel_drag", "Cancel drag"),
        ("ctrl+s", "save", "Save"),
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
    #board-header #view {
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
        self._card_drag = CardDragManager(self)
        self._column_drag = ColumnDragManager(self)

    def compose(self) -> ComposeResult:
        title = self.board.content.title or "ganban"
        yield EditableText(title, Static(title), TextEditor(), id="board-header")

        visible_columns = [c for c in self.board.columns if not c.hidden]

        with Horizontal(id="columns"):
            for column in visible_columns:
                yield ColumnWidget(column, self.board)
            yield AddColumn(self.board)

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
            self.board.content.title = event.new_value

    def on_click(self, event) -> None:
        """Show context menu on right-click on board header."""
        if event.button != 3:
            return
        header = self.query_one("#board-header", EditableText)
        if header.region.contains(event.screen_x, event.screen_y):
            event.stop()
            items = [MenuItem("Edit", "edit")]
            menu = ContextMenu(items, event.screen_x, event.screen_y)
            self.app.push_screen(menu, self._on_header_menu_closed)

    def _on_header_menu_closed(self, item: MenuItem | None) -> None:
        """Handle board header context menu selection."""
        if item and item.item_id == "edit":
            self.app.push_screen(BoardDetailModal(self.board), self._on_board_detail_closed)

    def _on_board_detail_closed(self, result: None) -> None:
        """Update header after board detail modal closes."""
        header = self.query_one("#board-header", EditableText)
        header.value = self.board.content.title or "ganban"

    async def action_save(self) -> None:
        """Save the board to git."""
        new_commit = await save_board(self.board)
        self.board.commit = new_commit
        self.notify("Saved")

    def on_card_widget_move_requested(self, event: CardWidget.MoveRequested) -> None:
        """Handle card move request."""
        event.stop()
        card = event.card
        col_name = event.target_column

        source_col = card._find_column()
        target_col = next((c for c in self.board.columns if c.name == col_name), None)
        if not target_col or target_col is source_col:
            return

        # Update model
        if source_col and card.link in source_col.links:
            source_col.links.remove(card.link)
            renumber_links(source_col)

        target_col.links.append(card.link)
        renumber_links(target_col)

        # Update UI - find target column widget and mount new card
        for col_widget in self.query(ColumnWidget):
            if col_widget.column is target_col:
                scroll = col_widget.query_one(VerticalScroll)
                add_widget = scroll.query_one(AddCard)
                new_card = CardWidget(card.link, card.title, self.board)
                scroll.mount(new_card, before=add_widget)
                break

        card.remove()

    def on_card_widget_delete_requested(self, event: CardWidget.DeleteRequested) -> None:
        """Handle card delete request."""
        event.stop()
        card = event.card
        col = card._find_column()
        if col and card.link in col.links:
            col.links.remove(card.link)
            renumber_links(col)
            card.remove()

    def on_add_card_card_created(self, event: AddCard.CardCreated) -> None:
        """Handle new card creation."""
        event.stop()
        # Find the column widget for this column and mount the new card
        for col_widget in self.query(ColumnWidget):
            if col_widget.column is event.column:
                scroll = col_widget.query_one(VerticalScroll)
                add_widget = scroll.query_one(AddCard)
                card_widget = CardWidget(event.card_link, event.title, self.board)
                scroll.mount(card_widget, before=add_widget)
                break

    def on_add_column_column_created(self, event: AddColumn.ColumnCreated) -> None:
        """Handle new column creation."""
        event.stop()
        columns_container = self.query_one("#columns", Horizontal)
        add_widget = columns_container.query_one(AddColumn)
        new_widget = ColumnWidget(event.column, self.board)
        columns_container.mount(new_widget, before=add_widget)

    def _move_column_to_index(self, col_widget: ColumnWidget, new_index: int) -> None:
        """Move column to new position in both model and UI."""
        column = col_widget.column

        # Update model
        self.board.columns.remove(column)
        self.board.columns.insert(new_index, column)

        # Renumber all columns
        for i, col in enumerate(self.board.columns):
            col.order = str(i + 1)
            col.path = build_column_path(col.order, col.name, col.hidden)

        # Sync UI to match model
        self._sync_column_order()

    def _sync_column_order(self) -> None:
        """Reorder column widgets to match model order."""
        columns_container = self.query_one("#columns", Horizontal)
        add_column = columns_container.query_one(AddColumn)
        widgets_by_column = {id(cw.column): cw for cw in self.query(ColumnWidget)}

        insert_before = add_column
        for column in reversed(self.board.columns):
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

        current_index = self.board.columns.index(col_widget.column)
        new_index = current_index + direction

        if new_index < 0 or new_index >= len(self.board.columns):
            return

        self._move_column_to_index(col_widget, new_index)

    def on_column_widget_delete_requested(self, event: ColumnWidget.DeleteRequested) -> None:
        """Handle column delete request."""
        event.stop()
        col_widget = event.column_widget

        # Remove from model
        if col_widget.column in self.board.columns:
            self.board.columns.remove(col_widget.column)

        # Remove from UI
        col_widget.remove()
