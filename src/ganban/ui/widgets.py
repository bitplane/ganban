"""Custom widgets for ganban UI."""

from textual.app import ComposeResult
from textual.containers import Container
from textual.message import Message
from textual.widgets import Static, TextArea


class _NonSelectableStatic(Static):
    """Static that doesn't allow text selection."""

    ALLOW_SELECT = False


class _EditArea(TextArea):
    """TextArea that emits Submit on Enter instead of inserting newline."""

    class Submit(Message):
        """Emitted when Enter is pressed."""

    class Cancel(Message):
        """Emitted when Escape is pressed."""

    def _on_key(self, event) -> None:
        if event.key == "enter":
            event.prevent_default()
            event.stop()
            self.post_message(self.Submit())
        elif event.key == "escape":
            event.prevent_default()
            event.stop()
            self.post_message(self.Cancel())
        else:
            super()._on_key(event)

    def on_blur(self) -> None:
        self.post_message(self.Submit())


class EditableLabel(Container):
    """A label that becomes editable when clicked."""

    DEFAULT_CSS = """
    EditableLabel {
        width: 100%;
        height: auto;
    }
    EditableLabel > Static {
        width: 100%;
    }
    EditableLabel > TextArea {
        width: 100%;
        height: auto;
        border: none;
        padding: 0;
    }
    """

    class Changed(Message):
        """Emitted when the label value changes."""

        def __init__(self, old_value: str, new_value: str) -> None:
            super().__init__()
            self.old_value = old_value
            self.new_value = new_value

        @property
        def control(self) -> "EditableLabel":
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
        self._value = self._clean(new_value)
        if not self._editing:
            self.query_one(Static).update(self._value)

    def compose(self) -> ComposeResult:
        yield _NonSelectableStatic(self._value)

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
        static = self.query_one(Static)
        static.remove()
        text_area = _EditArea(edit_text, soft_wrap=True, compact=True)
        text_area.cursor_type = "line"
        self.mount(text_area)
        text_area.focus()
        col = min(cursor_col, len(edit_text))
        text_area.cursor_location = (0, col)

    def _stop_editing(self, save: bool) -> None:
        if not self._editing:
            return
        self._editing = False
        text_area = self.query_one(_EditArea)
        new_value = self._clean(text_area.text)
        text_area.remove()
        self.mount(_NonSelectableStatic(self._value if not save else new_value))

        if save and new_value != self._value:
            old_value = self._value
            self._value = new_value
            self.post_message(self.Changed(old_value, new_value))

    def on__edit_area_submit(self) -> None:
        self._stop_editing(save=True)

    def on__edit_area_cancel(self) -> None:
        self._stop_editing(save=False)
