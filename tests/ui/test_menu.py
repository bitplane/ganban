"""Tests for the context menu system."""

import pytest
from textual.app import App

from ganban.ui.menu import ContextMenu, MenuItem, MenuList


class MenuTestApp(App):
    """Minimal app for testing menus."""

    def __init__(self, menu_items):
        super().__init__()
        self._menu_items = menu_items

    def on_mount(self):
        self.push_screen(ContextMenu(self._menu_items, x=0, y=0))


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
