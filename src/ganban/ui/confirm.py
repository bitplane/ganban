"""Compact inline confirmation widget."""

from textual.message import Message
from textual.widgets import Static

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

    DEFAULT_CSS = """
    ConfirmButton {
        width: 2;
        height: 1;
    }
    ConfirmButton:hover {
        background: $primary-darken-2;
    }
    """

    def __init__(self, icon: str = "❌", **kwargs) -> None:
        super().__init__(icon, **kwargs)

    def on_click(self, event) -> None:
        event.stop()
        menu = ContextMenu(
            [
                MenuRow(
                    MenuItem("🔙", item_id="cancel"),
                    MenuItem("❌", item_id="confirm"),
                ),
            ],
            event.screen_x,
            event.screen_y,
        )
        self.app.push_screen(menu, self._on_menu_closed)

    def _on_menu_closed(self, item: MenuItem | None) -> None:
        if item and item.item_id == "confirm":
            self.post_message(self.Confirmed())
