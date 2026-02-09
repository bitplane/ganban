"""Column widgets for ganban UI."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
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
from ganban.ui.drag import CardPlaceholder, DraggableMixin, DropTarget
from ganban.ui.menu import ContextMenu, MenuItem, MenuSeparator
from ganban.ui.edit import EditableText, TextEditor
from ganban.ui.watcher import NodeWatcherMixin


class ColumnWidget(NodeWatcherMixin, DraggableMixin, DropTarget, Vertical):
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
    ColumnWidget.compact CardWidget {
        height: 1;
        padding: 0 1;
        margin-bottom: 0;
    }
    ColumnWidget.compact CardWidget #card-header {
        display: none;
    }
    ColumnWidget.compact CardWidget #card-footer {
        display: none;
    }
    """

    HORIZONTAL_ONLY = True

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
        self._card_placeholder: CardPlaceholder | None = None

    def compose(self) -> ComposeResult:
        name = first_title(self.column.sections)
        yield EditableText(name, Static(name), TextEditor(), id="column-title")
        yield Rule()
        for card_id in self.column.links:
            yield CardWidget(card_id, self.board)
        yield AddCard(self.column, self.board)

    # -- DraggableMixin: column being dragged --

    def draggable_make_ghost(self):
        """Column IS the ghost — use self with CSS overlay positioning."""
        return self

    def _reposition_ghost(self, x: int, y: int) -> None:
        """Position column relative to its scroll container."""
        columns_container = self.screen.query_one("#columns", Horizontal)
        container_region = columns_container.region
        new_x = (x - self._drag_offset.x) - container_region.x + columns_container.scroll_x
        new_y = (y - self._drag_offset.y) - container_region.y + columns_container.scroll_y
        self.styles.offset = (new_x, new_y)

    def _drag_start(self, mouse_pos):
        """Override to set initial scroll-relative position before base logic."""
        super()._drag_start(mouse_pos)
        # Re-set offset for scroll-relative positioning
        columns_container = self.screen.query_one("#columns", Horizontal)
        container_region = columns_container.region
        col_region = self.region
        content_x = col_region.x - container_region.x + columns_container.scroll_x
        content_y = col_region.y - container_region.y + columns_container.scroll_y
        self.styles.offset = (content_x, content_y)

    def _drag_cleanup(self) -> None:
        """Reset offset instead of removing ghost (ghost is self)."""
        self.styles.offset = (0, 0)
        self._ghost = None
        self._dragging = False
        self._drag_offset = type(self._drag_offset)(0, 0)
        self.remove_class("dragging")
        if hasattr(self.screen, "_active_draggable"):
            self.screen._active_draggable = None

    def draggable_clicked(self) -> None:
        pass  # Click without drag - no action needed

    # -- DropTarget: column accepting card drops --

    def drag_over(self, draggable, x: int, y: int) -> bool:
        if not isinstance(draggable, CardWidget):
            return False
        insert_before = self._calculate_card_insert_position(draggable, y)
        self._ensure_card_placeholder(insert_before)
        return True

    def drag_away(self, draggable) -> None:
        if self._card_placeholder and self._card_placeholder.parent is not None:
            self._card_placeholder.remove()
        self._card_placeholder = None

    def try_drop(self, draggable, x: int, y: int) -> bool:
        if not isinstance(draggable, CardWidget):
            return False
        insert_before = self._calculate_card_insert_position(draggable, y)
        pos = self._calculate_card_model_position(draggable, insert_before)
        card_id = draggable.card_id

        move_card(draggable.board, card_id, self.column, position=pos)

        draggable.remove_class("dragging")
        if self._card_placeholder and self._card_placeholder.parent is not None:
            self._card_placeholder.remove()
        self._card_placeholder = None

        self.call_after_refresh(self._refocus_card, self, card_id)
        return True

    def _calculate_card_insert_position(self, draggable, screen_y: int) -> Static:
        add_widget = self.query_one(AddCard)
        visible_cards = [c for c in self.children if isinstance(c, CardWidget) and c is not draggable]

        for card in visible_cards:
            card_mid_y = card.region.y + card.region.height // 2
            if screen_y < card_mid_y:
                return card
        return add_widget

    def _ensure_card_placeholder(self, insert_before: Static) -> None:
        if self._card_placeholder is None:
            self._card_placeholder = CardPlaceholder()
            self.mount(self._card_placeholder, before=insert_before)
            return

        if self._card_placeholder.parent is self:
            children = list(self.children)
            placeholder_idx = children.index(self._card_placeholder)
            insert_idx = children.index(insert_before)
            if placeholder_idx + 1 == insert_idx:
                return
            self.move_child(self._card_placeholder, before=insert_before)
        else:
            if self._card_placeholder.parent is not None:
                self._card_placeholder.remove()
            self._card_placeholder = CardPlaceholder()
            self.mount(self._card_placeholder, before=insert_before)

    def _calculate_card_model_position(self, draggable, insert_before: Static) -> int:
        pos = 0
        for c in self.children:
            if c is insert_before:
                break
            if isinstance(c, CardWidget) and c is not draggable:
                pos += 1
        return pos

    # -- Other column behavior --

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
        view_label = "\u2261\u2261 Compact" if not self.has_class("compact") else "\u2fbf Card"
        items = [
            MenuItem(f"{ICON_COLUMN} {name}", disabled=True),
            MenuSeparator(),
            MenuItem(f"{ICON_EDIT} Edit", "edit"),
            MenuItem(f"{ICON_PALETTE} Color", "color", submenu=build_color_menu()),
            MenuItem(view_label, "compact"),
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
        """Handle DraggableMixin threshold first, then hover-focus tracking."""
        super().on_mouse_move(event)
        if self._drag_start_pos is not None or self.is_dragging:
            return
        # Hover-focus tracking
        focused = self.screen.focused
        for child in self.children:
            if child.can_focus and child.region.contains(event.screen_x, event.screen_y):
                if child is not focused and (focused is None or child not in focused.ancestors):
                    child.focus()
                return

    def on_mount(self) -> None:
        self._apply_color()
        self.set_class(bool(self.column.meta.compact), "compact")
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
        """Re-apply color and compact state when meta changes."""
        self._apply_color()
        self.set_class(bool(self.column.meta.compact), "compact")

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
            case "compact":
                self.column.meta.compact = None if self.column.meta.compact else True
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
