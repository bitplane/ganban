"""Compact inline confirmation widget."""

from textual.message import Message
from textual.widgets import Static

from ganban.ui.constants import ICON_BACK, ICON_DELETE
from ganban.ui.menu import ContextMenu, MenuItem, MenuRow


class ConfirmButton(Static):
    """A button that shows a confirm/cancel menu on click.

    Shows a single icon (default: ❌). When clicked, opens a context menu
    with ❌ (cancel) and ✅ (confirm). Emits Confirmed message on confirm.
    """

    class Confirmed(Message):
        """Emitted when the action is confirmed."""

        @property
        def control(self) -> "ConfirmButton":
            return self._sender

    def __init__(self, icon: str = ICON_DELETE, **kwargs) -> None:
        super().__init__(icon, **kwargs)

    def on_click(self, event) -> None:
        event.stop()
        menu = ContextMenu(
            [
                MenuRow(
                    MenuItem(ICON_BACK, item_id="cancel"),
                    MenuItem(ICON_DELETE, item_id="confirm"),
                ),
            ],
            event.screen_x,
            event.screen_y,
        )
        self.app.push_screen(menu, self._on_menu_closed)

    def _on_menu_closed(self, item: MenuItem | None) -> None:
        if item and item.item_id == "confirm":
            self.post_message(self.Confirmed())
