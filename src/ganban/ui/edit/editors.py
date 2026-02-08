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

    def start_editing(self, value: str) -> None:
        """Start editing. Called by EditableText."""
        self._done = False
        self.text = value
        self.cursor_location = (0, 0)
        self.focus()

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

    DEFAULT_CSS = """
    TextEditor {
        height: auto;
        padding: 0;
    }
    """

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

    DEFAULT_CSS = """
    MarkdownEditor {
        height: 100%;
        padding: 0;
    }
    """

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("compact", True)
        super().__init__(**kwargs)
