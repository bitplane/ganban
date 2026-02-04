"""Context menu system for ganban UI."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.events import Click
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Static


class MenuItem(Static):
    """A selectable menu item. Subclass for custom rendering."""

    class Selected(Message):
        """Posted when this item is selected."""

        def __init__(self, item: MenuItem) -> None:
            super().__init__()
            self.item = item

        @property
        def control(self) -> MenuItem:
            return self.item

    DEFAULT_CSS = """
    MenuItem {
        width: 100%;
        height: auto;
        padding: 0 1;
    }

    MenuItem:hover, MenuItem.-highlighted {
        background: $primary-darken-1;
    }

    MenuItem.-disabled {
        color: $text-muted;
    }

    MenuItem.-disabled:hover, MenuItem.-disabled.-highlighted {
        background: transparent;
    }

    MenuItem .submenu-arrow {
        dock: right;
    }
    """

    def __init__(
        self,
        label: str,
        item_id: str | None = None,
        submenu: list[MenuItem | MenuSeparator] | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__()
        self.label = label
        self.item_id = item_id
        self.submenu = submenu
        self.disabled = disabled

    def compose(self) -> ComposeResult:
        arrow = " >" if self.has_submenu else ""
        yield Static(f"{self.label}{arrow}")

    def on_mount(self) -> None:
        if self.disabled:
            self.add_class("-disabled")

    @property
    def has_submenu(self) -> bool:
        return self.submenu is not None and len(self.submenu) > 0

    def on_click(self, event: Click) -> None:
        event.stop()
        if not self.disabled:
            self.post_message(self.Selected(self))


class MenuSeparator(Static):
    """A horizontal separator line."""

    DEFAULT_CSS = """
    MenuSeparator {
        width: 100%;
        height: 1;
        border-bottom: solid $surface-lighten-1;
    }
    """


class MenuList(VerticalScroll):
    """Scrollable list of menu items with keyboard navigation."""

    DEFAULT_CSS = """
    MenuList {
        dock: top;
        height: auto;
        max-height: 80%;
        background: $surface;
        display: none;
    }

    MenuList.-visible {
        display: block;
    }
    """

    BINDINGS = [
        ("up", "cursor_up", "Up"),
        ("down", "cursor_down", "Down"),
        ("enter", "select", "Select"),
        ("right", "open_submenu", "Open submenu"),
    ]

    highlighted: reactive[int] = reactive(-1)

    def __init__(self, items: list[MenuItem | MenuSeparator]) -> None:
        super().__init__()
        self._items = items

    def compose(self) -> ComposeResult:
        yield from self._items

    def on_mount(self) -> None:
        self._set_width_from_content()
        self._move_highlight(1)

    def _set_width_from_content(self) -> None:
        """Set menu width based on longest item label."""
        max_len = 0
        has_submenu = False
        for item in self._items:
            if isinstance(item, MenuItem):
                max_len = max(max_len, len(item.label))
                if item.has_submenu:
                    has_submenu = True
        # Add space for submenu arrow " >" and padding (1 each side)
        width = max_len + (2 if has_submenu else 0) + 2
        self.styles.width = width

    def watch_highlighted(self, old: int, new: int) -> None:
        """Update highlight classes when selection changes."""
        items = list(self.query(MenuItem))
        if 0 <= old < len(items):
            items[old].remove_class("-highlighted")
        if 0 <= new < len(items):
            items[new].add_class("-highlighted")
            items[new].scroll_visible()

    def _move_highlight(self, direction: int) -> None:
        """Move highlight, skipping separators and disabled items."""
        items = list(self.query(MenuItem))
        if not items:
            return

        start = self.highlighted
        if start < 0:
            start = -1 if direction > 0 else len(items)

        pos = start + direction
        while 0 <= pos < len(items):
            if not items[pos].disabled:
                self.highlighted = pos
                return
            pos += direction

    def action_cursor_up(self) -> None:
        self._move_highlight(-1)

    def action_cursor_down(self) -> None:
        self._move_highlight(1)

    def action_select(self) -> None:
        items = list(self.query(MenuItem))
        if 0 <= self.highlighted < len(items):
            item = items[self.highlighted]
            if not item.disabled:
                item.post_message(MenuItem.Selected(item))

    def action_open_submenu(self) -> None:
        self.action_select()

    def on_mouse_move(self, event) -> None:
        """Highlight item under mouse."""
        items = list(self.query(MenuItem))
        for i, item in enumerate(items):
            if item.region.contains(event.screen_x, event.screen_y):
                if not item.disabled and self.highlighted != i:
                    self.highlighted = i
                break


class ContextMenu(ModalScreen[MenuItem | None]):
    """Context menu shown at a screen position."""

    class ItemSelected(Message):
        """Posted when an item is selected."""

        def __init__(self, item: MenuItem, control: ContextMenu) -> None:
            super().__init__()
            self.item = item
            self._control = control

        @property
        def control(self) -> ContextMenu:
            return self._control

    DEFAULT_CSS = """
    ContextMenu {
        background: transparent;
    }
    """

    BINDINGS = [
        ("escape", "close", "Close"),
        ("left", "close_submenu", "Close submenu"),
    ]

    def __init__(
        self,
        items: list[MenuItem | MenuSeparator],
        x: int,
        y: int,
    ) -> None:
        super().__init__()
        self._items = items
        self._x = x
        self._y = y
        self._menu_stack: list[MenuList] = []

    def compose(self) -> ComposeResult:
        menu = MenuList(self._items)
        yield menu

    def on_mount(self) -> None:
        menu = self.query_one(MenuList)
        self._menu_stack.append(menu)
        self._position_menu(menu, self._x, self._y)
        menu.focus()

    def _position_menu(
        self,
        menu: MenuList,
        x: int,
        y: int,
        parent_item: MenuItem | None = None,
    ) -> None:
        """Position menu on screen, flipping if necessary."""
        # Need to wait for layout to know menu size
        self.call_after_refresh(self._apply_position, menu, x, y, parent_item)

    def _apply_position(
        self,
        menu: MenuList,
        x: int,
        y: int,
        parent_item: MenuItem | None = None,
    ) -> None:
        """Apply position after layout is complete."""
        screen_width = self.app.size.width
        screen_height = self.app.size.height
        menu_width = menu.size.width
        menu_height = menu.size.height

        # Flip horizontally if needed
        if x + menu_width > screen_width:
            if parent_item:
                # Submenu: flip to left of parent
                parent_menu = self._menu_stack[-2] if len(self._menu_stack) > 1 else None
                if parent_menu:
                    x = parent_menu.region.x - menu_width
            else:
                x = screen_width - menu_width

        # Flip vertically if needed
        if y + menu_height > screen_height:
            y = screen_height - menu_height

        # Clamp to screen
        x = max(0, x)
        y = max(0, y)

        menu.styles.offset = (x, y)
        menu.add_class("-visible")

    def _open_submenu(self, item: MenuItem) -> None:
        """Open a submenu for the given item."""
        if not item.has_submenu:
            return

        # Close any existing submenus past the current level
        while len(self._menu_stack) > 1:
            old_menu = self._menu_stack.pop()
            old_menu.remove()

        submenu = MenuList(item.submenu)
        self.mount(submenu)
        self._menu_stack.append(submenu)

        # Position to the right of parent item
        parent_menu = self._menu_stack[-2]
        x = parent_menu.region.x + parent_menu.region.width
        y = item.region.y

        self._position_menu(submenu, x, y, item)
        submenu.focus()

    def on_menu_item_selected(self, event: MenuItem.Selected) -> None:
        """Handle item selection."""
        event.stop()
        item = event.item
        if item.has_submenu:
            self._open_submenu(item)
        else:
            self.post_message(self.ItemSelected(item, self))
            self.dismiss(item)

    def on_click(self, event: Click) -> None:
        """Dismiss menu when clicking outside."""
        for menu in self._menu_stack:
            if menu.region.contains(event.screen_x, event.screen_y):
                return
        self.dismiss(None)

    def action_close(self) -> None:
        """Close the entire menu."""
        self.dismiss(None)

    def action_close_submenu(self) -> None:
        """Close the current submenu and return to parent."""
        if len(self._menu_stack) > 1:
            submenu = self._menu_stack.pop()
            submenu.remove()
            self._menu_stack[-1].focus()
