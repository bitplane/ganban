"""Editable label widget."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import ContentSwitcher, Static

from ganban.ui.edit.text_area import SubmittingTextArea
from ganban.ui.events import ValueChanged
from ganban.ui.static import PlainStatic


class EditableLabel(Container):
    """A label that becomes editable when clicked."""

    DEFAULT_CSS = """
    EditableLabel {
        width: 100%;
        height: auto;
    }
    EditableLabel > ContentSwitcher {
        width: 100%;
        height: auto;
    }
    EditableLabel #view {
        width: 100%;
    }
    EditableLabel #edit {
        width: 100%;
        height: auto;
        border: none;
        padding: 0;
    }
    """

    class Changed(ValueChanged):
        """Emitted when the label value changes."""

        @property
        def control(self) -> EditableLabel:
            """The EditableLabel that changed."""
            return self._sender

    def __init__(self, value: str = "", click_to_edit: bool = False, **kwargs) -> None:
        super().__init__(**kwargs)
        self._value = self._clean(value)
        self._editing = False
        self._click_to_edit = click_to_edit

    @staticmethod
    def _clean(text: str) -> str:
        """Strip whitespace and remove newlines."""
        return " ".join(text.split())

    @property
    def value(self) -> str:
        return self._value

    @value.setter
    def value(self, new_value: str) -> None:
        new_value = self._clean(new_value)
        if new_value == self._value:
            return
        old_value = self._value
        self._value = new_value
        self.query_one("#view", Static).update(self._value)
        self.post_message(self.Changed(old_value, new_value))

    def compose(self) -> ComposeResult:
        with ContentSwitcher(initial="view"):
            yield PlainStatic(self._value, id="view")
            yield SubmittingTextArea(self._value, id="edit", soft_wrap=True, compact=True, disabled=True)

    def on_click(self, event) -> None:
        if self._click_to_edit and not self._editing:
            self.start_editing(cursor_col=event.x)

    def start_editing(self, text: str | None = None, cursor_col: int = 0) -> None:
        """Start editing the label.

        Args:
            text: Initial text for editor, or None to use current value
            cursor_col: Column position for cursor
        """
        if self._editing:
            return
        self._editing = True
        edit_text = self._value if text is None else text
        text_area = self.query_one("#edit", SubmittingTextArea)
        text_area.reset_submitted()
        text_area.disabled = False
        text_area.text = edit_text
        text_area.cursor_location = (0, min(cursor_col, len(edit_text)))
        self.query_one(ContentSwitcher).current = "edit"
        text_area.focus()

    def _stop_editing(self, save: bool) -> None:
        if not self._editing:
            return
        self._editing = False
        text_area = self.query_one("#edit", SubmittingTextArea)

        if save:
            self.value = text_area.text

        self.query_one(ContentSwitcher).current = "view"
        text_area.disabled = True

    def on_submitting_text_area_submitted(self) -> None:
        self._stop_editing(save=True)

    def on_submitting_text_area_cancelled(self) -> None:
        self._stop_editing(save=False)
