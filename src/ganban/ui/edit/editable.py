"""Editable text container widget."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.message import Message
from textual.widget import Widget
from textual.widgets import ContentSwitcher

from ganban.ui.edit.messages import Cancel, Save


class _FocusableView(Container):
    """Wrapper that makes the view focusable and triggers editing."""

    can_focus = True

    DEFAULT_CSS = """
    _FocusableView {
        width: 100%;
        height: auto;
    }
    """

    def on_focus(self) -> None:
        parent = self.parent
        while parent and not isinstance(parent, EditableText):
            parent = parent.parent
        if parent and not parent._skip_next_focus:
            parent._start_edit()
        if parent:
            parent._skip_next_focus = False


class EditableText(Container):
    """Orchestrates view/edit switching for any viewer + editor pair."""

    DEFAULT_CSS = """
    EditableText {
        width: 100%;
        height: auto;
    }
    EditableText > ContentSwitcher {
        width: 100%;
        height: auto;
    }
    EditableText #view {
        width: 100%;
    }
    EditableText #edit {
        width: 100%;
        height: auto;
    }
    """

    class Changed(Message):
        """Emitted when the value changes."""

        def __init__(self, old_value: str, new_value: str) -> None:
            super().__init__()
            self.old_value = old_value
            self.new_value = new_value

        @property
        def control(self) -> EditableText:
            """The EditableText that changed."""
            return self._sender

    def __init__(
        self,
        value: str,
        viewer: Widget,
        editor: Widget,
        *,
        clean: bool = True,
        placeholder: str = "",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._clean_enabled = clean
        self._placeholder = placeholder
        self._value = self._clean(value) if clean else value
        self._viewer = viewer
        self._editor = editor
        self._editing = False
        self._skip_next_focus = False

    def _clean(self, text: str) -> str:
        """Strip whitespace and remove newlines."""
        if self._clean_enabled:
            return " ".join(text.split())
        return text

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
        self._update_viewer()
        self.post_message(self.Changed(old_value, new_value))

    def _update_viewer(self) -> None:
        """Update viewer with current value, or placeholder if empty."""
        self._viewer.update(self._value or self._placeholder)

    def compose(self) -> ComposeResult:
        self._editor.id = "edit"
        with ContentSwitcher(initial="view"):
            yield _FocusableView(self._viewer, id="view")
            yield self._editor

    def focus(self, scroll_visible: bool = True) -> None:
        """Focus the widget - enters edit mode if not already editing."""
        if self._editing:
            self._editor.focus(scroll_visible)
        else:
            self.query_one("#view", _FocusableView).focus(scroll_visible)

    def on_click(self, event) -> None:
        if not self.disabled and not self._editing:
            self._start_edit(x=event.x, y=event.y)

    def _start_edit(self, x: int = 0, y: int = 0) -> None:
        if self._editing:
            return
        self._editing = True
        self.query_one(ContentSwitcher).current = "edit"
        self._editor.start_editing(self._value, x, y)

    def _stop_edit(self, save: bool, value: str = "") -> None:
        if not self._editing:
            return
        if save:
            self.value = value
        self._skip_next_focus = True
        self.query_one(ContentSwitcher).current = "view"
        self._editing = False

    def on_save(self, event: Save) -> None:
        event.stop()
        self._stop_edit(save=True, value=event.value)

    def on_cancel(self, event: Cancel) -> None:
        event.stop()
        self._stop_edit(save=False)
