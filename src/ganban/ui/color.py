"""Color picker for columns."""

from __future__ import annotations

from textual.color import Color
from textual.message import Message
from textual.widgets import Static

from ganban.ui.palette import COLORS, color_for_label
from ganban.ui.constants import ICON_PALETTE
from ganban.ui.menu import ContextMenu, MenuItem, MenuRow

__all__ = ["COLORS", "ColorButton", "ColorSwatch", "build_color_menu", "color_for_label"]


class ColorSwatch(MenuItem):
    """A colored menu item that uses outline for focus instead of background."""

    pass


def build_color_menu() -> list[MenuRow]:
    """Build a 4x4 color picker grid with clear in place of black."""
    color_iter = iter(COLORS.items())
    rows: list[MenuRow] = []
    for row_idx in range(4):
        items: list[MenuItem] = []
        for col_idx in range(4):
            if row_idx == 0 and col_idx == 0:
                items.append(MenuItem("\u274c", item_id="none"))
            else:
                _name, hex_val = next(color_iter)
                item = ColorSwatch("  ", item_id=hex_val)
                item.styles.background = Color.parse(hex_val)
                items.append(item)
        rows.append(MenuRow(*items))
    return rows


class ColorButton(Static):
    """A button that opens a color picker menu."""

    class ColorSelected(Message):
        """Posted when a color is selected."""

        def __init__(self, color: str | None) -> None:
            super().__init__()
            self.color = color

    def __init__(self, color: str | None = None, **kwargs) -> None:
        super().__init__(ICON_PALETTE, **kwargs)
        self._color = color

    def on_click(self, event) -> None:
        event.stop()
        menu = ContextMenu(build_color_menu(), event.screen_x, event.screen_y)
        self.app.push_screen(menu, self._on_menu_closed)

    def _on_menu_closed(self, item: MenuItem | None) -> None:
        if item is None:
            return
        color = None if item.item_id == "none" else item.item_id
        self._color = color
        self.post_message(self.ColorSelected(color))
