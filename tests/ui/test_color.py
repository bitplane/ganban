"""Tests for the color picker."""

import pytest
from textual.app import App, ComposeResult

from ganban.ui.color import (
    COLORS,
    ColorButton,
    ColorSwatch,
    build_color_menu,
)
from ganban.ui.menu import ContextMenu, MenuItem, MenuRow


# --- Sync tests (no app needed) ---


def test_build_color_menu_structure():
    """Menu has 4 rows of 4 items each."""
    rows = build_color_menu()
    assert len(rows) == 4
    assert all(isinstance(r, MenuRow) for r in rows)
    for row in rows:
        assert len(row._items) == 4


def test_build_color_menu_clear_item():
    """First item in first row is the clear button with id 'none'."""
    rows = build_color_menu()
    assert rows[0]._items[0].item_id == "none"


def test_build_color_menu_has_15_swatches():
    """Grid has 15 color swatches (16 cells minus clear)."""
    rows = build_color_menu()
    swatches = [item for row in rows for item in row._items if isinstance(item, ColorSwatch)]
    assert len(swatches) == 15


def test_build_color_menu_ids_match_colors():
    """Swatch item_ids match COLORS hex values in order."""
    rows = build_color_menu()
    ids = [item.item_id for row in rows for item in row._items if isinstance(item, ColorSwatch)]
    assert ids == list(COLORS.values())


def test_color_swatches_have_backgrounds():
    """Each swatch has a background style set."""
    rows = build_color_menu()
    for row in rows:
        for item in row._items:
            if isinstance(item, ColorSwatch):
                assert item.styles.background is not None


# --- Async tests ---


class ColorButtonApp(App):
    """Minimal app for testing the color button."""

    def __init__(self):
        super().__init__()
        self.selected_color = ...  # sentinel

    def compose(self) -> ComposeResult:
        yield ColorButton()

    def on_color_button_color_selected(self, event: ColorButton.ColorSelected) -> None:
        self.selected_color = event.color


@pytest.mark.asyncio
async def test_color_button_displays_icon():
    """Button shows the palette icon."""
    app = ColorButtonApp()
    async with app.run_test():
        btn = app.query_one(ColorButton)
        assert btn.content == "\U0001f3a8"


@pytest.mark.asyncio
async def test_click_opens_menu():
    """Clicking the button opens a ContextMenu."""
    app = ColorButtonApp()
    async with app.run_test() as pilot:
        btn = app.query_one(ColorButton)
        await pilot.click(btn)
        assert isinstance(app.screen, ContextMenu)


@pytest.mark.asyncio
async def test_menu_has_clear_and_swatches():
    """Opened menu has 1 clear item + 15 color swatches."""
    app = ColorButtonApp()
    async with app.run_test() as pilot:
        btn = app.query_one(ColorButton)
        await pilot.click(btn)

        swatches = list(app.screen.query(ColorSwatch))
        assert len(swatches) == 15

        all_items = list(app.screen.query(MenuItem))
        # 15 swatches + 1 clear = 16
        assert len(all_items) == 16


@pytest.mark.asyncio
async def test_selecting_color_emits_message():
    """Clicking a color swatch emits ColorSelected with the hex value."""
    app = ColorButtonApp()
    async with app.run_test() as pilot:
        btn = app.query_one(ColorButton)
        await pilot.click(btn)

        # First swatch should be "#800000" (red)
        swatch = app.screen.query(ColorSwatch).first()
        await pilot.click(swatch)

        assert app.selected_color == "#800000"


@pytest.mark.asyncio
async def test_selecting_clear_emits_none():
    """Clicking the clear item emits ColorSelected(None)."""
    app = ColorButtonApp()
    async with app.run_test() as pilot:
        btn = app.query_one(ColorButton)
        await pilot.click(btn)

        # Find the clear item (item_id == "none")
        clear_item = None
        for item in app.screen.query(MenuItem):
            if item.item_id == "none":
                clear_item = item
                break
        assert clear_item is not None

        await pilot.click(clear_item)
        assert app.selected_color is None


@pytest.mark.asyncio
async def test_escape_dismisses():
    """Pressing escape closes the menu without emitting a message."""
    app = ColorButtonApp()
    async with app.run_test() as pilot:
        btn = app.query_one(ColorButton)
        await pilot.click(btn)
        assert isinstance(app.screen, ContextMenu)

        await pilot.press("escape")
        assert not isinstance(app.screen, ContextMenu)
        assert app.selected_color is ...


@pytest.mark.asyncio
async def test_arrow_navigation_in_grid():
    """Down/up navigates between rows, left/right within rows."""
    app = ColorButtonApp()
    async with app.run_test() as pilot:
        btn = app.query_one(ColorButton)
        await pilot.click(btn)

        # First focused should be the clear item
        assert app.focused.item_id == "none"

        # Right within first row
        await pilot.press("right")
        assert app.focused.item_id == "#800000"

        # Down to second row, column 1 preserved -> "#800080" purple
        await pilot.press("down")
        assert app.focused.item_id == "#800080"

        # Up back, column 1 preserved -> "#800000" red
        await pilot.press("up")
        assert app.focused.item_id == "#800000"
