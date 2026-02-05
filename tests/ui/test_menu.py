"""Tests for the context menu system."""

import pytest
from textual.app import App

from ganban.ui.menu import ContextMenu, MenuItem, MenuList, MenuSeparator


class MenuTestApp(App):
    """Minimal app for testing menus."""

    def __init__(self, menu_items, x=0, y=0):
        super().__init__()
        self._menu_items = menu_items
        self._x = x
        self._y = y

    def on_mount(self):
        self.push_screen(ContextMenu(self._menu_items, x=self._x, y=self._y))


@pytest.mark.asyncio
async def test_menu_creates(menu_items):
    """Menu mounts with correct structure."""
    app = MenuTestApp(menu_items)
    async with app.run_test():
        screen = app.screen
        assert isinstance(screen, ContextMenu)

        # Should have one MenuList (the root)
        menu_lists = screen.query(MenuList)
        assert len(menu_lists) == 1

        # Root menu should have the right number of MenuItem widgets
        root_menu = menu_lists.first()
        items = root_menu.query(MenuItem)
        assert len(items) == 5  # Open, Save, Edit, View, Quit (separators aren't MenuItems)


@pytest.mark.asyncio
async def test_down_moves_focus(menu_items):
    """Down arrow moves focus to next enabled item."""
    app = MenuTestApp(menu_items)
    async with app.run_test() as pilot:
        # First enabled item should be focused on mount
        assert app.focused.item_id == "open"

        await pilot.press("down")
        # Save is disabled, so skip to Edit
        assert app.focused.item_id == "edit"

        await pilot.press("down")
        assert app.focused.item_id == "view"

        await pilot.press("down")
        assert app.focused.item_id == "quit"


@pytest.mark.asyncio
async def test_up_moves_focus(menu_items):
    """Up arrow moves focus to previous enabled item."""
    app = MenuTestApp(menu_items)
    async with app.run_test() as pilot:
        # Start at Open, go down to Edit first
        await pilot.press("down")
        assert app.focused.item_id == "edit"

        await pilot.press("up")
        # Save is disabled, so back to Open
        assert app.focused.item_id == "open"


@pytest.mark.asyncio
async def test_down_wraps_to_top(menu_items):
    """Down arrow at bottom wraps to top."""
    app = MenuTestApp(menu_items)
    async with app.run_test() as pilot:
        # Go to Quit (last item)
        await pilot.press("down")  # Edit
        await pilot.press("down")  # View
        await pilot.press("down")  # Quit
        assert app.focused.item_id == "quit"

        await pilot.press("down")
        # Should wrap to Open
        assert app.focused.item_id == "open"


@pytest.mark.asyncio
async def test_up_wraps_to_bottom(menu_items):
    """Up arrow at top wraps to bottom."""
    app = MenuTestApp(menu_items)
    async with app.run_test() as pilot:
        assert app.focused.item_id == "open"

        await pilot.press("up")
        # Should wrap to Quit
        assert app.focused.item_id == "quit"


@pytest.mark.asyncio
async def test_escape_dismisses(menu_items):
    """Escape key dismisses the menu."""
    app = MenuTestApp(menu_items)
    async with app.run_test() as pilot:
        assert isinstance(app.screen, ContextMenu)

        await pilot.press("escape")
        # Should return to default screen
        assert not isinstance(app.screen, ContextMenu)


@pytest.mark.asyncio
async def test_tab_dismisses(menu_items):
    """Tab key dismisses the menu."""
    app = MenuTestApp(menu_items)
    async with app.run_test() as pilot:
        assert isinstance(app.screen, ContextMenu)

        await pilot.press("tab")
        # Should return to default screen
        assert not isinstance(app.screen, ContextMenu)


@pytest.mark.asyncio
async def test_right_opens_submenu(menu_items):
    """Right arrow opens submenu when on item with submenu."""
    app = MenuTestApp(menu_items)
    async with app.run_test() as pilot:
        screen = app.screen
        # Go to Edit (has submenu)
        await pilot.press("down")
        assert app.focused.item_id == "edit"

        await pilot.press("right")
        # Should now have 2 menus open
        assert len(screen._open_menus) == 2
        # Focus should be on first item in submenu (Cut)
        assert app.focused.item_id == "cut"


@pytest.mark.asyncio
async def test_enter_opens_submenu(menu_items):
    """Enter key opens submenu when on item with submenu."""
    app = MenuTestApp(menu_items)
    async with app.run_test() as pilot:
        screen = app.screen
        # Go to Edit (has submenu)
        await pilot.press("down")
        assert app.focused.item_id == "edit"

        await pilot.press("enter")
        # Should now have 2 menus open
        assert len(screen._open_menus) == 2
        # Focus should be on first item in submenu (Cut)
        assert app.focused.item_id == "cut"


@pytest.mark.asyncio
async def test_left_returns_to_parent(menu_items):
    """Left arrow returns focus to parent menu."""
    app = MenuTestApp(menu_items)
    async with app.run_test() as pilot:
        screen = app.screen
        # Go to Edit and open submenu
        await pilot.press("down")
        await pilot.press("right")
        assert app.focused.item_id == "cut"
        assert len(screen._open_menus) == 2

        await pilot.press("left")
        # Focus should be back on Edit
        assert app.focused.item_id == "edit"
        # Submenu should be closed
        assert len(screen._open_menus) == 1


@pytest.mark.asyncio
async def test_moving_past_parent_closes_submenu(menu_items):
    """Moving focus away from submenu parent closes the submenu."""
    app = MenuTestApp(menu_items)
    async with app.run_test() as pilot:
        screen = app.screen
        # Go to Edit and open submenu by focusing (hover behavior)
        await pilot.press("down")
        assert app.focused.item_id == "edit"
        # Submenu should open when Edit is focused (has submenu)
        assert len(screen._open_menus) == 2

        # Move down to View - Edit's submenu should close
        await pilot.press("down")
        assert app.focused.item_id == "view"
        # Edit's submenu should be closed, View's should be open
        assert len(screen._open_menus) == 2
        assert screen._open_menus[-1].parent_item.item_id == "view"


@pytest.mark.asyncio
async def test_moving_to_item_without_submenu_closes_all(menu_items):
    """Moving to item without submenu closes any open submenus."""
    app = MenuTestApp(menu_items)
    async with app.run_test() as pilot:
        screen = app.screen
        # Go to Edit (opens submenu)
        await pilot.press("down")
        assert len(screen._open_menus) == 2

        # Move to Quit (no submenu)
        await pilot.press("down")  # View (has submenu)
        await pilot.press("down")  # Quit
        assert app.focused.item_id == "quit"
        # Only root menu should remain
        assert len(screen._open_menus) == 1


@pytest.mark.asyncio
async def test_all_disabled_menu_navigation(all_disabled_menu):
    """Up/down/enter in menu with all disabled items doesn't crash."""
    app = MenuTestApp(all_disabled_menu)
    async with app.run_test() as pilot:
        # No item should be focused (all disabled)
        assert not isinstance(app.focused, MenuItem)

        # Pressing up/down/enter should not crash
        await pilot.press("down")
        await pilot.press("up")
        await pilot.press("enter")

        # Still no MenuItem focused, menu still open
        assert not isinstance(app.focused, MenuItem)
        assert isinstance(app.screen, ContextMenu)


def find_item(screen, item_id):
    """Find a MenuItem by its item_id."""
    for item in screen.query(MenuItem):
        if item.item_id == item_id:
            return item
    return None


@pytest.mark.asyncio
async def test_hover_focuses_item(menu_items):
    """Hovering over a menu item focuses it."""
    app = MenuTestApp(menu_items)
    async with app.run_test() as pilot:
        # Initially focused on Open
        assert app.focused.item_id == "open"

        # Hover over Quit (last item)
        quit_item = find_item(app.screen, "quit")
        await pilot.hover(quit_item)

        assert app.focused.item_id == "quit"


@pytest.mark.asyncio
async def test_hover_opens_submenu(menu_items):
    """Hovering over item with submenu opens it."""
    app = MenuTestApp(menu_items)
    async with app.run_test() as pilot:
        screen = app.screen
        assert len(screen._open_menus) == 1

        # Hover over Edit (has submenu)
        edit_item = find_item(screen, "edit")
        await pilot.hover(edit_item)

        assert app.focused.item_id == "edit"
        assert len(screen._open_menus) == 2
        assert screen._open_menus[-1].parent_item.item_id == "edit"


@pytest.mark.asyncio
async def test_enter_selects_leaf_item(menu_items):
    """Enter key on leaf item selects it and dismisses menu."""
    app = MenuTestApp(menu_items)
    async with app.run_test() as pilot:
        # Open is focused, it's a leaf item
        assert app.focused.item_id == "open"

        await pilot.press("enter")

        # Menu should be dismissed
        assert not isinstance(app.screen, ContextMenu)


@pytest.mark.asyncio
async def test_left_at_root_does_nothing(menu_items):
    """Left arrow at root level (no submenu open) does nothing."""
    app = MenuTestApp(menu_items)
    async with app.run_test() as pilot:
        screen = app.screen
        assert app.focused.item_id == "open"
        assert len(screen._open_menus) == 1

        await pilot.press("left")

        # Still at root, still focused on Open
        assert app.focused.item_id == "open"
        assert len(screen._open_menus) == 1


@pytest.mark.asyncio
async def test_click_selects_leaf_item(menu_items):
    """Clicking a leaf item selects it and dismisses menu."""
    app = MenuTestApp(menu_items)
    async with app.run_test() as pilot:
        quit_item = find_item(app.screen, "quit")
        await pilot.click(quit_item)

        # Menu should be dismissed
        assert not isinstance(app.screen, ContextMenu)


@pytest.mark.asyncio
async def test_click_opens_submenu(menu_items):
    """Clicking item with submenu opens it."""
    app = MenuTestApp(menu_items)
    async with app.run_test() as pilot:
        screen = app.screen
        edit_item = find_item(screen, "edit")
        await pilot.click(edit_item)

        # Submenu should be open, focus on first item
        assert len(screen._open_menus) == 2
        assert app.focused.item_id == "cut"


@pytest.mark.asyncio
async def test_click_outside_dismisses(menu_items):
    """Clicking outside the menu dismisses it."""
    app = MenuTestApp(menu_items)
    async with app.run_test() as pilot:
        assert isinstance(app.screen, ContextMenu)

        # Click away from the menu (menu is at top-left)
        await pilot.click(offset=(50, 10))

        # Menu should be dismissed
        assert not isinstance(app.screen, ContextMenu)


@pytest.mark.asyncio
async def test_click_separator_does_not_dismiss(menu_items):
    """Clicking a separator (inside menu but not on item) doesn't dismiss."""
    app = MenuTestApp(menu_items)
    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, ContextMenu)

        # Find and click a separator
        separator = screen.query_one(MenuSeparator)
        await pilot.click(separator)

        # Menu should still be open
        assert isinstance(app.screen, ContextMenu)


@pytest.mark.asyncio
async def test_menu_repositions_near_right_edge(menu_items):
    """Menu repositions when it would overflow right edge."""
    # Position menu near right edge (default terminal is 80x24)
    app = MenuTestApp(menu_items, x=75, y=0)
    async with app.run_test():
        screen = app.screen
        root_menu = screen._open_menus[0]

        # Menu should have been repositioned to fit on screen
        # x offset should be less than 75
        assert root_menu.styles.offset.x.value < 75


@pytest.mark.asyncio
async def test_menu_repositions_near_bottom_edge(menu_items):
    """Menu repositions when it would overflow bottom edge."""
    # Position menu near bottom edge
    app = MenuTestApp(menu_items, x=0, y=20)
    async with app.run_test():
        screen = app.screen
        root_menu = screen._open_menus[0]

        # Menu should have been repositioned to fit on screen
        # y offset should be less than 20
        assert root_menu.styles.offset.y.value < 20


@pytest.mark.asyncio
async def test_submenu_flips_left_near_right_edge(menu_items):
    """Submenu opens to the left when near right edge."""
    # Position menu so submenu would overflow right (80 - menu_width ~8 = 72)
    app = MenuTestApp(menu_items, x=72, y=0)
    async with app.run_test() as pilot:
        screen = app.screen
        root_menu = screen._open_menus[0]

        # Open Edit submenu
        await pilot.press("down")  # Edit
        assert app.focused.item_id == "edit"

        # Submenu should be open
        assert len(screen._open_menus) == 2
        submenu = screen._open_menus[1]

        # Submenu should be positioned to the left of root menu
        assert submenu.styles.offset.x.value < root_menu.styles.offset.x.value


# --- MenuRow tests ---


@pytest.mark.asyncio
async def test_down_enters_row(menu_with_row):
    """Down from above a row focuses the row's first item."""
    app = MenuTestApp(menu_with_row)
    async with app.run_test() as pilot:
        assert app.focused.item_id == "normal"

        await pilot.press("down")
        assert app.focused.item_id == "a"


@pytest.mark.asyncio
async def test_down_from_row_exits(menu_with_row):
    """Down from inside a row moves to next item below."""
    app = MenuTestApp(menu_with_row)
    async with app.run_test() as pilot:
        await pilot.press("down")  # into row -> "a"
        await pilot.press("right")  # -> "b"
        assert app.focused.item_id == "b"

        await pilot.press("down")
        assert app.focused.item_id == "below"


@pytest.mark.asyncio
async def test_up_enters_row_from_below(menu_with_row):
    """Up from below a row focuses the row's active item."""
    app = MenuTestApp(menu_with_row)
    async with app.run_test() as pilot:
        # Navigate down to "below"
        await pilot.press("down")  # -> "a"
        await pilot.press("down")  # -> "below"
        assert app.focused.item_id == "below"

        await pilot.press("up")
        assert app.focused.item_id == "a"


@pytest.mark.asyncio
async def test_up_from_row_exits(menu_with_row):
    """Up from inside a row moves to previous item above."""
    app = MenuTestApp(menu_with_row)
    async with app.run_test() as pilot:
        await pilot.press("down")  # -> "a"
        assert app.focused.item_id == "a"

        await pilot.press("up")
        assert app.focused.item_id == "normal"


@pytest.mark.asyncio
async def test_right_moves_within_row(menu_with_row):
    """Right arrow moves to next item in row."""
    app = MenuTestApp(menu_with_row)
    async with app.run_test() as pilot:
        await pilot.press("down")  # -> "a"
        assert app.focused.item_id == "a"

        await pilot.press("right")
        assert app.focused.item_id == "b"

        await pilot.press("right")
        assert app.focused.item_id == "c"


@pytest.mark.asyncio
async def test_left_moves_within_row(menu_with_row):
    """Left arrow moves to previous item in row."""
    app = MenuTestApp(menu_with_row)
    async with app.run_test() as pilot:
        await pilot.press("down")  # -> "a"
        await pilot.press("right")  # -> "b"
        await pilot.press("right")  # -> "c"
        assert app.focused.item_id == "c"

        await pilot.press("left")
        assert app.focused.item_id == "b"

        await pilot.press("left")
        assert app.focused.item_id == "a"


@pytest.mark.asyncio
async def test_right_at_row_end_selects(menu_with_row):
    """Right at end of row selects the item (no submenu)."""
    app = MenuTestApp(menu_with_row)
    async with app.run_test() as pilot:
        await pilot.press("down")  # -> "a"
        await pilot.press("right")  # -> "b"
        await pilot.press("right")  # -> "c"
        assert app.focused.item_id == "c"

        await pilot.press("right")
        # "c" has no submenu, so it gets selected and menu dismisses
        assert not isinstance(app.screen, ContextMenu)


@pytest.mark.asyncio
async def test_left_at_row_start_does_close_submenu(menu_with_row):
    """Left at start of row does close submenu behavior (noop at root)."""
    app = MenuTestApp(menu_with_row)
    async with app.run_test() as pilot:
        await pilot.press("down")  # -> "a"
        assert app.focused.item_id == "a"

        await pilot.press("left")
        # At root level, close submenu is a no-op, focus stays
        assert app.focused.item_id == "a"
        assert isinstance(app.screen, ContextMenu)


@pytest.mark.asyncio
async def test_row_remembers_active_item(menu_with_row):
    """Row remembers which item was last focused."""
    app = MenuTestApp(menu_with_row)
    async with app.run_test() as pilot:
        await pilot.press("down")  # -> "a"
        await pilot.press("right")  # -> "b"
        assert app.focused.item_id == "b"

        await pilot.press("down")  # -> "below"
        assert app.focused.item_id == "below"

        await pilot.press("up")  # -> back to row, should be "b"
        assert app.focused.item_id == "b"


@pytest.mark.asyncio
async def test_enter_selects_row_item(menu_with_row):
    """Enter on item in row selects it and dismisses."""
    app = MenuTestApp(menu_with_row)
    async with app.run_test() as pilot:
        await pilot.press("down")  # -> "a"
        await pilot.press("right")  # -> "b"
        assert app.focused.item_id == "b"

        await pilot.press("enter")
        assert not isinstance(app.screen, ContextMenu)


@pytest.mark.asyncio
async def test_click_row_item(menu_with_row):
    """Clicking an item in a row selects it."""
    app = MenuTestApp(menu_with_row)
    async with app.run_test() as pilot:
        b_item = find_item(app.screen, "b")
        await pilot.click(b_item)

        assert not isinstance(app.screen, ContextMenu)


@pytest.mark.asyncio
async def test_row_wrapping_up_from_top(menu_with_row):
    """Up from first item wraps to last."""
    app = MenuTestApp(menu_with_row)
    async with app.run_test() as pilot:
        assert app.focused.item_id == "normal"

        await pilot.press("up")
        assert app.focused.item_id == "below"


@pytest.mark.asyncio
async def test_row_wrapping_down_from_bottom(menu_with_row):
    """Down from last item wraps to first."""
    app = MenuTestApp(menu_with_row)
    async with app.run_test() as pilot:
        await pilot.press("down")  # -> "a"
        await pilot.press("down")  # -> "below"
        assert app.focused.item_id == "below"

        await pilot.press("down")
        assert app.focused.item_id == "normal"
