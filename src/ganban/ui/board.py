"""Board screen showing kanban columns and cards."""

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.geometry import Offset
from textual.screen import Screen
from textual.widgets import Static

from ganban.models import Board
from ganban.writer import build_column_path, save_board
from ganban.ui.card import AddCardWidget, CardWidget
from ganban.ui.column import ColumnWidget, AddColumnWidget, ColumnPlaceholder
from ganban.ui.drag import DragStart
from ganban.ui.widgets import EditableLabel


class DropPlaceholder(Static):
    """Placeholder showing where a dragged card will drop."""

    DEFAULT_CSS = """
    DropPlaceholder {
        width: 100%;
        height: 3;
        margin-bottom: 1;
        border: dashed $primary;
        background: $surface-darken-1;
    }
    """


class DragOverlay(Static):
    """Floating overlay showing the card being dragged."""

    DEFAULT_CSS = """
    DragOverlay {
        layer: overlay;
        width: 22;
        height: auto;
        padding: 0 1;
        border: solid $primary;
        background: $surface;
    }
    """

    def __init__(self, title: str):
        super().__init__(title)


def _renumber_column_links(column) -> None:
    """Renumber all links in a column to sequential zero-padded positions."""
    width = len(str(len(column.links))) if column.links else 1
    for i, link in enumerate(column.links):
        link.position = str(i + 1).zfill(width)


class CardDragManager:
    """Manages card drag-and-drop state and operations."""

    def __init__(self, screen: "BoardScreen"):
        self.screen = screen
        self.dragging: CardWidget | None = None
        self.overlay: DragOverlay | None = None
        self.placeholder: DropPlaceholder | None = None
        self.drag_offset: Offset = Offset(0, 0)
        self.target_scroll: VerticalScroll | None = None
        self.insert_before: Static | None = None

    @property
    def active(self) -> bool:
        return self.dragging is not None

    def start(self, card: CardWidget, mouse_offset: Offset) -> None:
        self.dragging = card
        card.add_class("dragging")

        card_region = card.region
        self.drag_offset = Offset(
            mouse_offset.x - card_region.x,
            mouse_offset.y - card_region.y,
        )

        self.overlay = DragOverlay(card.title)
        self.overlay.styles.offset = (card_region.x, card_region.y)
        self.screen.mount(self.overlay)

        self.placeholder = DropPlaceholder()
        card.parent.mount(self.placeholder, after=card)

        self.screen.capture_mouse()

    def update_position(self, screen_x: int, screen_y: int) -> None:
        if not self.dragging or not self.overlay:
            return

        new_x = screen_x - self.drag_offset.x
        new_y = screen_y - self.drag_offset.y
        self.overlay.styles.offset = (new_x, new_y)

        self._update_placeholder_position(screen_x, screen_y)

    def _update_placeholder_position(self, screen_x: int, screen_y: int) -> None:
        if not self.placeholder:
            return

        column_widget = self._find_nearest_column(screen_x)
        if not column_widget:
            return

        scroll = column_widget.query_one(VerticalScroll)
        insert_before = self._calculate_insert_position(scroll, screen_y)

        self.target_scroll = scroll
        self.insert_before = insert_before

        self._move_placeholder(scroll, insert_before)

    def _find_nearest_column(self, screen_x: int) -> ColumnWidget | None:
        columns = list(self.screen.query(ColumnWidget))
        if not columns:
            return None

        def column_distance(col):
            region = col.region
            if screen_x < region.x:
                return region.x - screen_x
            if screen_x >= region.x + region.width:
                return screen_x - (region.x + region.width - 1)
            return 0

        return min(columns, key=column_distance)

    def _calculate_insert_position(self, scroll: VerticalScroll, screen_y: int) -> Static:
        add_widget = scroll.query_one(AddCardWidget)
        visible_cards = [c for c in scroll.children if isinstance(c, CardWidget) and c is not self.dragging]

        for card in visible_cards:
            card_mid_y = card.region.y + card.region.height // 2
            if screen_y < card_mid_y:
                return card
        return add_widget

    def _move_placeholder(self, scroll: VerticalScroll, insert_before: Static) -> None:
        if self.placeholder.parent is scroll:
            children = list(scroll.children)
            placeholder_idx = children.index(self.placeholder)
            insert_idx = children.index(insert_before)
            if placeholder_idx + 1 == insert_idx:
                return
            scroll.move_child(self.placeholder, before=insert_before)
        else:
            if self.placeholder.parent is not None:
                self.placeholder.remove()
            scroll.mount(self.placeholder, before=insert_before)

    def finish(self) -> None:
        if not self.dragging or not self.target_scroll:
            self.cancel()
            return

        self.screen.release_mouse()

        card = self.dragging
        target_scroll = self.target_scroll
        insert_before = self.insert_before
        target_column = target_scroll.parent.column

        source_column = self._find_source_column(card)
        if source_column and card.link in source_column.links:
            source_column.links.remove(card.link)
            _renumber_column_links(source_column)

        actual_pos = self._calculate_model_position(target_scroll, insert_before, card)
        target_column.links.insert(actual_pos, card.link)
        _renumber_column_links(target_column)

        new_card = CardWidget(card.link, card.title, self.screen.board)
        target_scroll.mount(new_card, before=insert_before)
        card.remove()

        self._cleanup()

    def _find_source_column(self, card: CardWidget):
        for col in self.screen.board.columns:
            if any(link.card_id == card.link.card_id for link in col.links):
                return col
        return None

    def _calculate_model_position(self, scroll: VerticalScroll, insert_before: Static, card: CardWidget) -> int:
        pos = 0
        for c in scroll.children:
            if c is insert_before:
                break
            if isinstance(c, CardWidget) and c is not card:
                pos += 1
        return pos

    def cancel(self) -> None:
        if not self.dragging:
            return

        self.screen.release_mouse()
        self.dragging.remove_class("dragging")
        self._cleanup()

    def _cleanup(self) -> None:
        if self.placeholder and self.placeholder.parent is not None:
            self.placeholder.remove()
        if self.overlay:
            self.overlay.remove()

        self.dragging = None
        self.placeholder = None
        self.overlay = None
        self.target_scroll = None
        self.insert_before = None


class ColumnDragManager:
    """Manages column drag-and-drop state and operations."""

    def __init__(self, screen: "BoardScreen"):
        self.screen = screen
        self.dragging: ColumnWidget | None = None
        self.placeholder: ColumnPlaceholder | None = None
        self.insert_before: Static | None = None
        self.drag_offset: Offset = Offset(0, 0)

    @property
    def active(self) -> bool:
        return self.dragging is not None

    def start(self, column_widget: ColumnWidget, mouse_offset: Offset) -> None:
        self.dragging = column_widget
        column_widget.add_class("dragging")

        col_region = column_widget.region
        self.drag_offset = Offset(
            mouse_offset.x - col_region.x,
            mouse_offset.y - col_region.y,
        )

        column_widget.styles.offset = (col_region.x, col_region.y)

        columns_container = self.screen.query_one("#columns", Horizontal)
        self.placeholder = ColumnPlaceholder()
        columns_container.mount(self.placeholder, after=column_widget)

        self.screen.capture_mouse()

    def update_position(self, screen_x: int, screen_y: int) -> None:
        if not self.dragging:
            return

        new_x = screen_x - self.drag_offset.x
        new_y = screen_y - self.drag_offset.y
        self.dragging.styles.offset = (new_x, new_y)

        self._update_placeholder_position(screen_x)

    def _update_placeholder_position(self, screen_x: int) -> None:
        if not self.placeholder:
            return

        columns_container = self.screen.query_one("#columns", Horizontal)
        visible_columns = [
            c for c in columns_container.children if isinstance(c, ColumnWidget) and c is not self.dragging
        ]

        add_column = columns_container.query_one(AddColumnWidget)

        if not visible_columns:
            self.insert_before = add_column
            return

        insert_before = add_column

        for col in visible_columns:
            col_mid_x = col.region.x + col.region.width // 2
            if screen_x < col_mid_x:
                insert_before = col
                break

        self.insert_before = insert_before

        children = list(columns_container.children)
        placeholder_idx = children.index(self.placeholder)
        insert_idx = children.index(insert_before)
        if placeholder_idx + 1 != insert_idx:
            columns_container.move_child(self.placeholder, before=insert_before)

    def finish(self) -> None:
        if not self.dragging:
            self.cancel()
            return

        self.screen.release_mouse()

        column_widget = self.dragging
        column = column_widget.column
        insert_before = self.insert_before

        columns_container = self.screen.query_one("#columns", Horizontal)

        new_index = self._calculate_model_position(columns_container, column_widget)

        self.screen.board.columns.remove(column)
        self.screen.board.columns.insert(new_index, column)

        for i, col in enumerate(self.screen.board.columns):
            col.order = str(i + 1)
            col.path = build_column_path(col.order, col.name, col.hidden)

        column_widget.remove_class("dragging")
        column_widget.styles.offset = (0, 0)
        columns_container.move_child(column_widget, before=insert_before)

        self._cleanup()

    def _calculate_model_position(self, container: Horizontal, dragging: ColumnWidget) -> int:
        pos = 0
        for child in container.children:
            if child is self.insert_before:
                break
            if isinstance(child, ColumnWidget) and child is not dragging:
                pos += 1
        return pos

    def cancel(self) -> None:
        if not self.dragging:
            return

        self.screen.release_mouse()
        self.dragging.remove_class("dragging")
        self.dragging.styles.offset = (0, 0)
        self._cleanup()

    def _cleanup(self) -> None:
        if self.placeholder and self.placeholder.parent is not None:
            self.placeholder.remove()

        self.dragging = None
        self.placeholder = None
        self.insert_before = None


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
