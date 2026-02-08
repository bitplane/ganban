"""Column widgets for ganban UI."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.geometry import Offset
from textual.message import Message
from textual.color import Color, ColorParseError
from textual.widgets import Rule, Static

from ganban.model.card import move_card
from ganban.model.column import create_column, rename_column
from ganban.model.node import Node
from ganban.parser import first_title
from ganban.ui.card import AddCard, CardWidget
from ganban.ui.color import build_color_menu
from ganban.ui.constants import (
    ICON_BACK,
    ICON_COLUMN,
    ICON_CONFIRM,
    ICON_DELETE,
    ICON_EDIT,
    ICON_MOVE_LEFT,
    ICON_MOVE_RIGHT,
    ICON_PALETTE,
)
from ganban.ui.detail import ColumnDetailModal
from ganban.ui.drag import DraggableMixin
from ganban.ui.menu import ContextMenu, MenuItem, MenuSeparator
from ganban.ui.edit import EditableText, TextEditor
from ganban.ui.watcher import NodeWatcherMixin


class ColumnWidget(NodeWatcherMixin, DraggableMixin, Vertical):
    """A single column on the board."""

    DEFAULT_CSS = """
    ColumnWidget {
        width: 1fr;
        height: auto;
        min-height: 100%;
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

    class ArchiveRequested(Message):
        """Posted when column should be archived."""

        def __init__(self, column_widget: "ColumnWidget") -> None:
            super().__init__()
            self.column_widget = column_widget

    def __init__(self, column: Node, board: Node):
        self._init_watcher()
        Vertical.__init__(self)
        self._init_draggable()
        self.column = column
        self.board = board

    def compose(self) -> ComposeResult:
        name = first_title(self.column.sections)
        yield EditableText(name, Static(name), TextEditor(), id="column-title")
        yield Rule()
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
            rename_column(self.board, self.column, event.new_value)

    def on_click(self, event) -> None:
        """Show context menu on right-click."""
        if event.button == 3:
            event.stop()
            self.show_context_menu(event.screen_x, event.screen_y)

    def show_context_menu(self, x: int | None = None, y: int | None = None) -> None:
        if x is None or y is None:
            region = self.region
            x = region.x + region.width // 2
            y = region.y + region.height // 2
        name = first_title(self.column.sections)
        col_index = self._get_column_index()
        visible_count = sum(1 for c in self.board.columns if not c.hidden)
        items = [
            MenuItem(f"{ICON_COLUMN} {name}", disabled=True),
            MenuSeparator(),
            MenuItem(f"{ICON_EDIT} Edit", "edit"),
            MenuItem(f"{ICON_PALETTE} Color", "color", submenu=build_color_menu()),
            MenuSeparator(),
            MenuItem(f"{ICON_MOVE_LEFT} Move Left", "move_left", disabled=(col_index == 0)),
            MenuItem(f"{ICON_MOVE_RIGHT} Move Right", "move_right", disabled=(col_index >= visible_count - 1)),
            MenuSeparator(),
            MenuItem(f"{ICON_DELETE} Archive", "archive"),
        ]
        self.app.push_screen(ContextMenu(items, x, y), self._on_menu_closed)

    def on_key(self, event) -> None:
        """Arrow key navigation and shift+arrow card movement."""
        if event.key not in (
            "up",
            "down",
            "left",
            "right",
            "shift+up",
            "shift+down",
            "shift+left",
            "shift+right",
        ):
            return

        focused = self.screen.focused
        focusable = [c for c in self.children if c.can_focus]
        if focused not in focusable:
            return

        idx = focusable.index(focused)

        if event.key == "up" and idx > 0:
            focusable[idx - 1].focus()
        elif event.key == "down" and idx < len(focusable) - 1:
            focusable[idx + 1].focus()
        elif event.key in ("left", "right"):
            direction = -1 if event.key == "left" else 1
            siblings = list(self.parent.children)
            my_idx = siblings.index(self)
            new_idx = my_idx + direction
            if 0 <= new_idx < len(siblings):
                target = siblings[new_idx]
                target_focusable = [c for c in target.children if c.can_focus]
                if target_focusable:
                    target_focusable[min(idx, len(target_focusable) - 1)].focus()
        elif event.key.startswith("shift+") and isinstance(focused, CardWidget):
            self._move_card(focused, event.key)

        event.prevent_default()
        event.stop()

    def _move_card(self, card: CardWidget, key: str) -> None:
        """Move a card via shift+arrow by updating the model."""
        links = list(self.column.links)
        card_idx = links.index(card.card_id)
        card_id = card.card_id

        if key in ("shift+up", "shift+down"):
            swap_idx = card_idx + (-1 if key == "shift+up" else 1)
            if 0 <= swap_idx < len(links):
                move_card(self.board, card_id, self.column, position=swap_idx)
                self.call_after_refresh(lambda: self._refocus_card(self, card_id))
        elif key in ("shift+left", "shift+right"):
            direction = -1 if key == "shift+left" else 1
            siblings = list(self.parent.children)
            my_idx = siblings.index(self)
            new_idx = my_idx + direction
            if 0 <= new_idx < len(siblings) and hasattr(siblings[new_idx], "column"):
                target = siblings[new_idx]
                move_card(self.board, card_id, target.column, position=min(card_idx, len(target.column.links)))
                self.call_after_refresh(lambda: self._refocus_card(target, card_id))

    @staticmethod
    def _refocus_card(column: "ColumnWidget", card_id: str) -> None:
        """Focus a card by id within a specific column."""
        for card in column.query(CardWidget):
            if card.card_id == card_id:
                card.focus()
                return

    def on_mouse_move(self, event) -> None:
        """Focus the child widget under the mouse cursor."""
        focused = self.screen.focused
        for child in self.children:
            if child.can_focus and child.region.contains(event.screen_x, event.screen_y):
                if child is not focused and (focused is None or child not in focused.ancestors):
                    child.focus()
                return

    def on_mount(self) -> None:
        self._apply_color()
        self.node_watch(self.column, "sections", self._on_sections_changed)
        self.node_watch(self.column, "meta", self._on_meta_changed)
        self.node_watch(self.column, "links", self._on_links_changed)

    def _on_links_changed(self, node, key, old, new) -> None:
        """Sync card children to match column.links."""
        new_links = list(self.column.links) if self.column.links else []
        existing = {c.card_id: c for c in self.query(CardWidget)}
        new_ids = set(new_links)

        # Remove cards no longer in links
        for card_id, widget in existing.items():
            if card_id not in new_ids:
                widget.remove()

        # Add missing cards and reorder
        add_card = self.query_one(AddCard)
        for card_id in new_links:
            if card_id not in existing:
                widget = CardWidget(card_id, self.board)
                self.mount(widget, before=add_card)
                existing[card_id] = widget

        # Reorder to match links
        for card_id in reversed(new_links):
            self.move_child(existing[card_id], before=add_card)
            add_card = existing[card_id]

    def _on_meta_changed(self, node, key, old, new) -> None:
        """Re-apply color when meta changes."""
        self._apply_color()

    def _on_sections_changed(self, node, key, old, new) -> None:
        """Sync UI when sections title changes."""
        keys = self.column.sections.keys()
        if not keys:
            return  # transient empty state during rename_first_key rebuild
        new_name = keys[0]
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
            except ColorParseError:
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
                self.app.push_screen(ColumnDetailModal(self.column, self.board))
            case "move_left":
                self.post_message(self.MoveRequested(self, -1))
            case "move_right":
                self.post_message(self.MoveRequested(self, 1))
            case "archive":
                self._confirm_archive()

    def _confirm_archive(self) -> None:
        name = first_title(self.column.sections)
        region = self.region
        x = region.x + region.width // 2
        y = region.y + region.height // 2
        items = [
            MenuItem(f"{ICON_DELETE} Archive {name}?", disabled=True),
            MenuSeparator(),
            MenuItem(f"{ICON_CONFIRM} Confirm", "confirm"),
            MenuItem(f"{ICON_BACK} Cancel", "cancel"),
        ]
        self.app.push_screen(ContextMenu(items, x, y), self._on_archive_confirmed)

    def _on_archive_confirmed(self, item: MenuItem | None) -> None:
        if item and item.item_id == "confirm":
            self.post_message(self.ArchiveRequested(self))

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
