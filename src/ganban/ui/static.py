"""Static widget variants."""

from textual.events import Click
from textual.widgets import Static

from ganban.ui.constants import ICON_CLOSE


class PlainStatic(Static):
    """Static that doesn't allow text selection."""

    ALLOW_SELECT = False


class CloseButton(Static):
    """Close button that triggers the screen's close action."""

    DEFAULT_CSS = """
    CloseButton {
        width: auto;
        height: 1;
        padding: 0 1;
    }
    CloseButton:hover {
        background: $error;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(ICON_CLOSE, **kwargs)

    async def on_click(self, event: Click) -> None:
        event.stop()
        await self.screen.run_action("close")
