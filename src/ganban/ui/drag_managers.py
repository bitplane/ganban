"""Drag-and-drop managers for board elements."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.containers import Horizontal
from textual.geometry import Offset
from textual.widgets import Static

if TYPE_CHECKING:
    from ganban.ui.board import BoardScreen
    from ganban.ui.card import CardWidget
    from ganban.ui.column import ColumnWidget


class CardPlaceholder(Static):
    """Placeholder showing where a dragged card will drop."""

    DEFAULT_CSS = """
    CardPlaceholder {
        width: 100%;
        height: 3;
        margin-bottom: 1;
        border: dashed $primary;
        background: $surface-darken-1;
    }
    """


class DragGhost(Static):
    """Floating overlay showing the card being dragged."""

    DEFAULT_CSS = """
    DragGhost {
        layer: overlay;
        height: auto;
    }
    """

    def __init__(self, card: CardWidget):
        super().__init__()
        self._card = card

    def compose(self):
        from ganban.ui.card import CardWidget

        yield CardWidget(self._card.card_id, self._card.board)


class ColumnPlaceholder(Static):
    """Placeholder showing where a dragged column will drop."""

    DEFAULT_CSS = """
    ColumnPlaceholder {
        width: 1fr;
        min-width: 25;
        max-width: 25;
        height: 100%;
        border: dashed $primary;
        background: $surface-darken-1;
    }
    """


class CardDragManager:
    """Manages card drag-and-drop state and operations."""

    def __init__(self, screen: BoardScreen):
        self.screen = screen
        self.dragging: CardWidget | None = None
        self.overlay: DragGhost | None = None
        self.placeholder: CardPlaceholder | None = None
        self.drag_offset: Offset = Offset(0, 0)
        self.target_column: ColumnWidget | None = None
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

        self.overlay = DragGhost(card)
        self.overlay.styles.width = card_region.width
        self.overlay.styles.offset = (card_region.x, card_region.y)
        self.screen.mount(self.overlay)

        self.placeholder = CardPlaceholder()
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

        insert_before = self._calculate_insert_position(column_widget, screen_y)

        self.target_column = column_widget
        self.insert_before = insert_before

        self._move_placeholder(column_widget, insert_before)

    def _find_nearest_column(self, screen_x: int) -> ColumnWidget | None:
        from ganban.ui.column import ColumnWidget

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

    def _calculate_insert_position(self, column: ColumnWidget, screen_y: int) -> Static:
        from ganban.ui.card import AddCard, CardWidget

        add_widget = column.query_one(AddCard)
        visible_cards = [c for c in column.children if isinstance(c, CardWidget) and c is not self.dragging]

        for card in visible_cards:
            card_mid_y = card.region.y + card.region.height // 2
            if screen_y < card_mid_y:
                return card
        return add_widget

    def _move_placeholder(self, column: ColumnWidget, insert_before: Static) -> None:
        if self.placeholder.parent is column:
            children = list(column.children)
            placeholder_idx = children.index(self.placeholder)
            insert_idx = children.index(insert_before)
            if placeholder_idx + 1 == insert_idx:
                return
            column.move_child(self.placeholder, before=insert_before)
        else:
            if self.placeholder.parent is not None:
                self.placeholder.remove()
            column.mount(self.placeholder, before=insert_before)

    def finish(self) -> None:
        if not self.dragging or not self.target_column:
            self.cancel()
            return

        self.screen.release_mouse()

        from ganban.ui.card import CardWidget

        card = self.dragging
        target_col_widget = self.target_column
        insert_before = self.insert_before
        target_column = target_col_widget.column

        source_column = card._find_column()
        if source_column:
            links = list(source_column.links)
            if card.card_id in links:
                links.remove(card.card_id)
                source_column.links = links

        actual_pos = self._calculate_model_position(target_col_widget, insert_before, card)
        links = list(target_column.links)
        links.insert(actual_pos, card.card_id)
        target_column.links = links

        new_card = CardWidget(card.card_id, self.screen.board)
        target_col_widget.mount(new_card, before=insert_before)
        card.remove()

        self._cleanup()

    def _calculate_model_position(self, column: ColumnWidget, insert_before: Static, card: CardWidget) -> int:
        from ganban.ui.card import CardWidget

        pos = 0
        for c in column.children:
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
        self.target_column = None
        self.insert_before = None


class ColumnDragManager:
    """Manages column drag-and-drop state and operations."""

    def __init__(self, screen: BoardScreen):
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

        from ganban.ui.column import AddColumn, ColumnWidget

        columns_container = self.screen.query_one("#columns", Horizontal)
        visible_columns = [
            c for c in columns_container.children if isinstance(c, ColumnWidget) and c is not self.dragging
        ]

        add_column = columns_container.query_one(AddColumn)

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
        columns_container = self.screen.query_one("#columns", Horizontal)
        new_index = self._calculate_model_position(columns_container, column_widget)

        column_widget.remove_class("dragging")
        column_widget.styles.offset = (0, 0)

        self.screen._move_column_to_index(column_widget, new_index)

        self._cleanup()

    def _calculate_model_position(self, container: Horizontal, dragging: ColumnWidget) -> int:
        from ganban.ui.column import ColumnWidget

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
