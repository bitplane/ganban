"""Editor widgets that emit Save/Cancel messages."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.widgets import TextArea

from ganban.ui.edit.messages import Cancel, Save

if TYPE_CHECKING:
    from textual.events import Key


class BaseEditor(TextArea):
    """Base editor that emits Save/Cancel."""

    SAVE_ON_ENTER = True

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._done = False
        self._click_screen: tuple[int, int] | None = None

    def start_editing(self, value: str) -> None:
        """Start editing. Called by EditableText."""
        self._done = False
        self.text = value
        if self._click_screen is None:
            self.cursor_location = (0, 0)
        self.focus()

    def on_resize(self, event) -> None:
        """Apply pending click position once we know our layout."""
        if self._click_screen is None:
            return
        screen_x, screen_y = self._click_screen
        self._click_screen = None
        region = self.region
        x = screen_x - region.x
        y = screen_y - region.y
        pos = type("_Pos", (), {"x": x, "y": y})()
        self.cursor_location = self.get_target_document_location(pos)

    def _finish(self, save: bool) -> None:
        if self._done:
            return
        self._done = True
        self.post_message(Save(self.text) if save else Cancel())

    async def _on_key(self, event: Key) -> None:
        if event.key == "escape":
            event.prevent_default()
            event.stop()
            self._finish(save=False)
        elif event.key == "enter" and self.SAVE_ON_ENTER:
            event.prevent_default()
            event.stop()
            self._finish(save=True)
        else:
            await super()._on_key(event)

    def on_blur(self) -> None:
        self._finish(save=True)


class TextEditor(BaseEditor):
    """Single-line editor. Enter saves."""

    SAVE_ON_ENTER = True

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("soft_wrap", True)
        kwargs.setdefault("compact", True)
        super().__init__(**kwargs)


class NumberEditor(TextEditor):
    """Single-line numeric editor. Validates input is a number on save."""

    def _finish(self, save: bool) -> None:
        if save and self.text.strip():
            try:
                float(self.text)
            except ValueError:
                save = False
        super()._finish(save)


class MarkdownEditor(BaseEditor):
    """Multi-line editor. Enter inserts newline."""

    SAVE_ON_ENTER = False

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("compact", True)
        kwargs.setdefault("language", "markdown")
        super().__init__(**kwargs)
