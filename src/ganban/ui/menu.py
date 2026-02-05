"""Context menu system for ganban UI."""

from __future__ import annotations

from rich.cells import cell_len
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.events import Click
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Static


class MenuItem(Static, can_focus=True):
    """A focusable menu item."""

    class Clicked(Message):
        """Posted when this item is clicked."""

        def __init__(self, item: MenuItem) -> None:
            super().__init__()
            self.item = item

    DEFAULT_CSS = """
    MenuItem {
        width: 100%;
        height: auto;
        padding: 0 1;
    }

    MenuItem:focus {
        background: $primary-darken-1;
    }

    MenuItem:disabled {
        color: $text-muted;
    }

    MenuItem:disabled:focus {
        background: transparent;
    }
    """

    def __init__(
        self,
        label: str,
        item_id: str | None = None,
        submenu: list[MenuItem | MenuSeparator] | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(disabled=disabled)
        self.label = label
        self.item_id = item_id
        self.submenu = submenu

    def compose(self) -> ComposeResult:
        arrow = " >" if self.has_submenu else ""
        yield Static(f"{self.label}{arrow}")

    @property
    def has_submenu(self) -> bool:
        return self.submenu is not None and len(self.submenu) > 0

    def on_click(self, event: Click) -> None:
        event.stop()
        self.post_message(self.Clicked(self))

    def on_mouse_move(self, event) -> None:
        if not self.has_focus:
            self.focus()


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
    """Container for menu items."""

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

    class Ready(Message):
        """Posted when menu has been laid out and has a size."""

        def __init__(self, menu: MenuList) -> None:
            super().__init__()
            self.menu = menu

    def __init__(
        self,
        items: list[MenuItem | MenuSeparator],
        parent_item: MenuItem | None = None,
    ) -> None:
        super().__init__()
        self._items = items
        self.parent_item = parent_item
        self._ready_sent: bool = False
        self._target_x: int = 0
        self._target_y: int = 0

    def compose(self) -> ComposeResult:
        yield from self._items

    def on_mount(self) -> None:
        self._set_width_from_content()

    def on_resize(self, event) -> None:
        """Notify when we have actual dimensions."""
        if not self._ready_sent and self.size.width > 0 and self.size.height > 0:
            self._ready_sent = True
            self.post_message(self.Ready(self))

    def _set_width_from_content(self) -> None:
        """Set menu width based on content."""
        max_len = 0
        has_submenu = False
        has_custom_widget = False
        for item in self._items:
            if isinstance(item, MenuItem):
                max_len = max(max_len, cell_len(item.label))
                if item.has_submenu:
                    has_submenu = True
            elif not isinstance(item, MenuSeparator):
                # Custom widget - let it determine its own width
                has_custom_widget = True
        if has_custom_widget:
            self.styles.width = "auto"
        else:
            width = max_len + (2 if has_submenu else 0) + 2
            self.styles.width = width

    def _focus_first_enabled(self) -> None:
        """Focus the first enabled menu item."""
        for item in self.query(MenuItem):
            if not item.disabled:
                item.focus()
                break

    def get_focusable_items(self) -> list[MenuItem]:
        """Return list of enabled menu items."""
        return [item for item in self.query(MenuItem) if not item.disabled]


class ContextMenu(ModalScreen[MenuItem | None]):
    """Context menu with keyboard navigation."""

    class ItemSelected(Message):
        """Posted when an item is selected."""

        def __init__(self, item: MenuItem) -> None:
            super().__init__()
            self.item = item

    DEFAULT_CSS = """
    ContextMenu {
        background: transparent;
    }
    """

    BINDINGS = [
        ("up", "focus_prev", "Up"),
        ("down", "focus_next", "Down"),
        ("enter", "select_or_enter", "Select"),
        ("right", "select_or_enter", "Enter submenu"),
        ("left", "close_submenu", "Back"),
        ("escape", "close", "Close"),
        ("tab", "close", "Close"),
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
        self._open_menus: list[MenuList] = []

    def compose(self) -> ComposeResult:
        menu = MenuList(self._items)
        yield menu

    def on_mount(self) -> None:
        menu = self.query_one(MenuList)
        self._open_menus.append(menu)
        self._position_menu(menu, self._x, self._y)
        menu._focus_first_enabled()

    @property
    def _focused_item(self) -> MenuItem | None:
        """The currently focused MenuItem."""
        focused = self.app.focused
        return focused if isinstance(focused, MenuItem) else None

    def _menu_for_item(self, item: MenuItem) -> MenuList:
        """Find which menu contains an item."""
        return next(menu for menu in self._open_menus if item in menu.query(MenuItem))

    def _position_menu(self, menu: MenuList, x: int, y: int) -> None:
        """Show menu at initial position. Edge adjustment happens on_menu_list_ready."""
        menu._target_x = x
        menu._target_y = y
        menu.styles.offset = (x, y)
        menu.add_class("-visible")

    def on_menu_list_ready(self, event: MenuList.Ready) -> None:
        """Adjust menu position when we know actual dimensions."""
        event.stop()
        menu = event.menu
        x = menu._target_x
        y = menu._target_y

        screen_width = self.app.size.width
        screen_height = self.app.size.height
        menu_width = menu.size.width
        menu_height = menu.size.height

        needs_adjustment = False

        if x + menu_width > screen_width:
            needs_adjustment = True
            if menu.parent_item:
                parent_menu = self._menu_for_item(menu.parent_item)
                x = parent_menu.region.x - menu_width
            else:
                x = screen_width - menu_width

        if y + menu_height > screen_height:
            needs_adjustment = True
            y = screen_height - menu_height

        if needs_adjustment:
            x = max(0, x)
            y = max(0, y)
            menu.styles.offset = (x, y)

    def _open_submenu(self, parent_item: MenuItem) -> MenuList:
        """Open submenu for item. Caller must verify has_submenu first."""
        # Already open?
        if self._open_menus[-1].parent_item is parent_item:
            return self._open_menus[-1]

        submenu = MenuList(parent_item.submenu, parent_item=parent_item)
        self.mount(submenu)
        self._open_menus.append(submenu)

        # Position to the right of parent item
        parent_menu = self._menu_for_item(parent_item)
        x = parent_menu.region.x + parent_menu.region.width
        y = parent_item.region.y

        self._position_menu(submenu, x, y)
        return submenu

    def _close_menus_after(self, menu: MenuList) -> None:
        """Close all menus deeper than the given menu."""
        idx = self._open_menus.index(menu)
        while len(self._open_menus) > idx + 1:
            self._open_menus.pop().remove()

    def _on_item_focused(self, item: MenuItem) -> None:
        """Handle focus moving to an item."""
        menu = self._menu_for_item(item)
        if menu:
            # Check if we're coming back from this item's own submenu
            coming_back = len(self._open_menus) > 1 and self._open_menus[-1].parent_item is item
            self._close_menus_after(menu)
            # Open submenu unless we just came back from it
            if item.has_submenu and not coming_back:
                self._open_submenu(item)

    def on_descendant_focus(self, event) -> None:
        """React to any focus change within the menu."""
        if isinstance(event.widget, MenuItem):
            self._on_item_focused(event.widget)

    def action_focus_prev(self) -> None:
        """Focus the previous enabled item in current menu (wraps around)."""
        focused = self._focused_item
        if not focused:
            return
        menu = self._menu_for_item(focused)
        items = menu.get_focusable_items()
        idx = items.index(focused)
        items[(idx - 1) % len(items)].focus()

    def action_focus_next(self) -> None:
        """Focus the next enabled item in current menu (wraps around)."""
        focused = self._focused_item
        if not focused:
            return
        menu = self._menu_for_item(focused)
        items = menu.get_focusable_items()
        idx = items.index(focused)
        items[(idx + 1) % len(items)].focus()

    def action_select_or_enter(self) -> None:
        """Select leaf item or enter submenu."""
        focused = self._focused_item
        if not focused:
            return
        if focused.has_submenu:
            self._open_submenu(focused)._focus_first_enabled()
        else:
            self.post_message(self.ItemSelected(focused))
            self.dismiss(focused)

    def action_close_submenu(self) -> None:
        """Move focus back to parent item."""
        if len(self._open_menus) <= 1:
            return
        parent_item = self._open_menus[-1].parent_item
        if parent_item:
            parent_item.focus()
            # on_descendant_focus will clean up via _close_menus_after

    def action_close(self) -> None:
        """Close the entire menu."""
        self.dismiss(None)

    def on_menu_item_clicked(self, event: MenuItem.Clicked) -> None:
        """Handle item click."""
        event.stop()
        item = event.item
        if item.has_submenu:
            self._open_submenu(item)._focus_first_enabled()
        else:
            self.post_message(self.ItemSelected(item))
            self.dismiss(item)

    def on_click(self, event: Click) -> None:
        """Dismiss menu when clicking outside."""
        for menu in self._open_menus:
            if menu.region.contains(event.screen_x, event.screen_y):
                return
        self.dismiss(None)

    def on_calendar_menu_item_selected(self, event) -> None:
        """Handle calendar menu item selection."""
        event.stop()
        self.dismiss(event.item)
