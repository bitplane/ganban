"""Editable markdown widget."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import ContentSwitcher, Markdown

from ganban.ui.edit.text_area import MarkdownTextArea
from ganban.ui.events import ValueChanged


class EditableMarkdown(Container):
    """Markdown that becomes editable when clicked."""

    DEFAULT_CSS = """
    EditableMarkdown {
        width: 100%;
        height: 1fr;
    }
    EditableMarkdown > ContentSwitcher {
        width: 100%;
        height: 100%;
    }
    EditableMarkdown #view {
        width: 100%;
        height: 100%;
        padding: 0;
    }
    EditableMarkdown #edit {
        width: 100%;
        height: 100%;
        border: none;
        padding: 0;
    }
    """

    class Changed(ValueChanged):
        """Emitted when the markdown content changes."""

        @property
        def control(self) -> EditableMarkdown:
            """The EditableMarkdown that changed."""
            return self._sender

    def __init__(self, value: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._value = value
        self._editing = False

    @property
    def value(self) -> str:
        return self._value

    @value.setter
    def value(self, new_value: str) -> None:
        self._value = new_value
        self.query_one("#view", Markdown).update(self._value)

    def compose(self) -> ComposeResult:
        with ContentSwitcher(initial="view"):
            yield Markdown(self._value, id="view")
            yield MarkdownTextArea(self._value, id="edit", disabled=True)

    def on_click(self, event) -> None:
        if not self._editing:
            # Use screen coordinates relative to our region, not the clicked child
            view = self.query_one("#view", Markdown)
            row = event.screen_y - view.region.y
            col = event.screen_x - view.region.x
            self.start_editing(row=row, col=col)

    def start_editing(self, row: int = 0, col: int = 0) -> None:
        """Start editing the markdown content."""
        if self._editing:
            return
        self._editing = True
        text_area = self.query_one("#edit", MarkdownTextArea)
        text_area.reset_submitted()
        text_area.disabled = False
        text_area.text = self._value
        lines = self._value.split("\n")
        row = min(row, len(lines) - 1) if lines else 0
        col = min(col, len(lines[row])) if lines else 0
        text_area.cursor_location = (row, col)
        self.query_one(ContentSwitcher).current = "edit"
        text_area.focus()

    def _stop_editing(self, save: bool) -> None:
        if not self._editing:
            return
        self._editing = False
        text_area = self.query_one("#edit", MarkdownTextArea)
        new_value = text_area.text

        if save and new_value != self._value:
            old_value = self._value
            self._value = new_value
            self.query_one("#view", Markdown).update(self._value)
            self.post_message(self.Changed(old_value, new_value))

        self.query_one(ContentSwitcher).current = "view"
        text_area.disabled = True

    def on_submitting_text_area_submitted(self) -> None:
        self._stop_editing(save=True)

    def on_submitting_text_area_cancelled(self) -> None:
        self._stop_editing(save=False)
