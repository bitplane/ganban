"""Tests for the confirm button widget."""

import pytest
from textual.app import App, ComposeResult

from ganban.ui.confirm import ConfirmButton
from ganban.ui.constants import ICON_CONFIRM
from ganban.ui.menu import ContextMenu, MenuItem


class ConfirmApp(App):
    """Minimal app for testing confirm button."""

    def __init__(self):
        super().__init__()
        self.confirmed = False
        self.confirmed_control = None

    def compose(self) -> ComposeResult:
        yield ConfirmButton()

    def on_confirm_button_confirmed(self, event: ConfirmButton.Confirmed) -> None:
        self.confirmed = True
        self.confirmed_control = event.control


@pytest.fixture
def app():
    return ConfirmApp()


@pytest.mark.asyncio
async def test_displays_icon(app):
    """Button displays the trash icon by default."""
    async with app.run_test():
        btn = app.query_one(ConfirmButton)
        assert btn.content == ICON_CONFIRM


@pytest.mark.asyncio
async def test_custom_icon():
    """Button can display a custom icon."""
    app = App()
    app.compose = lambda: [ConfirmButton(icon="🔥")]
    async with app.run_test():
        btn = app.query_one(ConfirmButton)
        assert btn.content == "🔥"


@pytest.mark.asyncio
async def test_click_opens_menu(app):
    """Clicking button opens context menu."""
    async with app.run_test() as pilot:
        btn = app.query_one(ConfirmButton)
        await pilot.click(btn)
        assert isinstance(app.screen, ContextMenu)


@pytest.mark.asyncio
async def test_menu_has_cancel_and_confirm(app):
    """Menu has cancel and confirm options."""
    async with app.run_test() as pilot:
        btn = app.query_one(ConfirmButton)
        await pilot.click(btn)

        items = list(app.screen.query(MenuItem))
        assert len(items) == 2
        assert items[0].item_id == "cancel"
        assert items[1].item_id == "confirm"


@pytest.mark.asyncio
async def test_confirm_emits_message(app):
    """Selecting confirm emits Confirmed message."""
    async with app.run_test() as pilot:
        btn = app.query_one(ConfirmButton)
        await pilot.click(btn)

        # Navigate right to confirm item and select it
        await pilot.press("right")
        assert app.focused.item_id == "confirm"
        await pilot.press("enter")
        assert app.confirmed is True


@pytest.mark.asyncio
async def test_cancel_does_not_emit(app):
    """Selecting cancel does not emit Confirmed message."""
    async with app.run_test() as pilot:
        btn = app.query_one(ConfirmButton)
        await pilot.click(btn)

        # Cancel is first item (already focused), select it
        assert app.focused.item_id == "cancel"
        await pilot.press("enter")
        assert app.confirmed is False


@pytest.mark.asyncio
async def test_escape_dismisses_without_confirm(app):
    """Pressing escape dismisses menu without confirming."""
    async with app.run_test() as pilot:
        btn = app.query_one(ConfirmButton)
        await pilot.click(btn)
        assert isinstance(app.screen, ContextMenu)

        await pilot.press("escape")
        assert not isinstance(app.screen, ContextMenu)
        assert app.confirmed is False


@pytest.mark.asyncio
async def test_confirmed_event_control_is_button(app):
    """Confirmed event's control property returns the ConfirmButton."""
    async with app.run_test() as pilot:
        btn = app.query_one(ConfirmButton)
        await pilot.click(btn)

        confirm_item = None
        for item in app.screen.query(MenuItem):
            if item.item_id == "confirm":
                confirm_item = item
                break

        await pilot.click(confirm_item)
        assert app.confirmed_control is btn
