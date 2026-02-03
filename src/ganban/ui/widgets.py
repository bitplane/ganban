"""Custom widgets for ganban UI."""

from textual.app import ComposeResult
from textual.containers import Container
from textual.message import Message
from textual.widgets import Input, Static


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
    EditableLabel > Input {
        width: 100%;
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

    def __init__(self, value: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._value = self._clean(value)
        self._editing = False

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
        yield Static(self._value)

    def on_click(self) -> None:
        if not self._editing:
            self._start_editing()

    def _start_editing(self) -> None:
        self._editing = True
        static = self.query_one(Static)
        static.remove()
        input_widget = Input(value=self._value, compact=True)
        self.mount(input_widget)
        input_widget.focus()

    def _stop_editing(self, save: bool) -> None:
        if not self._editing:
            return
        self._editing = False
        input_widget = self.query_one(Input)
        new_value = self._clean(input_widget.value)
        input_widget.remove()
        self.mount(Static(self._value if not save else new_value))

        if save and new_value != self._value:
            old_value = self._value
            self._value = new_value
            self.post_message(self.Changed(old_value, new_value))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self._stop_editing(save=True)

    def on_input_blurred(self, event: Input.Blurred) -> None:
        self._stop_editing(save=True)

    def key_escape(self) -> None:
        if self._editing:
            self._stop_editing(save=False)
