"""Board screen showing kanban columns and cards."""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen

from ganban.models import Board
from ganban.writer import save_board
from ganban.ui.card import CardWidget
from ganban.ui.column import ColumnWidget, AddColumnWidget
from ganban.ui.drag import DragStart
from ganban.ui.drag_managers import CardDragManager, ColumnDragManager
from ganban.ui.widgets import EditableLabel


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
        yield EditableLabel(title, click_to_edit=True, id="board-header")

        visible_columns = [c for c in self.board.columns if not c.hidden]

        with Horizontal(id="columns"):
            for column in visible_columns:
                yield ColumnWidget(column, self.board)
            yield AddColumnWidget(self.board)

    def on_drag_start(self, event: DragStart) -> None:
        """Handle drag start from a card."""
        if isinstance(event.widget, CardWidget):
            event.stop()
            self._card_drag.start(event.widget, event.mouse_offset)

    def on_column_widget_drag_start(self, event: ColumnWidget.DragStart) -> None:
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

    def on_editable_label_changed(self, event: EditableLabel.Changed) -> None:
        """Update board title when header is edited."""
        header = self.query_one("#board-header", EditableLabel)
        if event.control is header:
            event.stop()
            self.board.content.title = event.new_value

    async def action_save(self) -> None:
        """Save the board to git."""
        new_commit = await save_board(self.board)
        self.board.commit = new_commit
        self.notify("Saved")
