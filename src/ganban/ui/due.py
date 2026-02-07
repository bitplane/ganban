"""Due date widget with inline editing."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Static

from ganban.model.node import Node
from ganban.ui.cal import DateButton, date_diff
from ganban.ui.confirm import ConfirmButton
from ganban.ui.constants import ICON_CALENDAR


class DueDateLabel(Horizontal):
    """Shows due date text, swaps to delete confirmation on hover."""

    DEFAULT_CSS = """
    DueDateLabel { width: auto; height: 1; }
    DueDateLabel .due-text { width: auto; height: 1; }
    DueDateLabel .due-text:hover { background: $primary-darken-2; }
    DueDateLabel.overdue .due-text { color: $error; }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        yield Static("", classes="due-text")
        btn = ConfirmButton(classes="due-clear")
        btn.display = False
        yield btn

    def set_label(self, text: str) -> None:
        self.query_one(".due-text", Static).update(text)
        self.query_one(".due-text", Static).display = bool(text)
        self.query_one(".due-clear", ConfirmButton).display = False

    def on_enter(self, event) -> None:
        text_widget = self.query_one(".due-text", Static)
        if text_widget.display:
            text_widget.display = False
            self.query_one(".due-clear", ConfirmButton).display = True

    def on_leave(self, event) -> None:
        text_widget = self.query_one(".due-text", Static)
        clear_widget = self.query_one(".due-clear", ConfirmButton)
        if clear_widget.display:
            clear_widget.display = False
            text_widget.display = bool(text_widget.render())


class DueDateWidget(Container):
    """Inline due date display with calendar picker.

    Reads and writes ``meta.due`` on the given Node directly,
    and watches the node so external changes (e.g. the meta editor)
    are reflected immediately.
    """

    DEFAULT_CSS = """
    DueDateWidget {
        width: auto;
        height: 1;
    }
    DueDateWidget Horizontal {
        width: auto;
        height: 1;
    }
    DueDateWidget #due-picker {
        margin-right: 1;
    }
    """

    def __init__(self, meta: Node, **kwargs) -> None:
        super().__init__(**kwargs)
        self.meta = meta
        self._unwatch: Callable | None = None
        self._suppressing: bool = False

    @property
    def due(self) -> date | None:
        due_str = self.meta.due
        if due_str:
            try:
                return date.fromisoformat(due_str)
            except (ValueError, TypeError):
                return None
        return None

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield DateButton(selected=self.due, icon=ICON_CALENDAR, id="due-picker")
            yield DueDateLabel(id="due-label")

    def on_mount(self) -> None:
        self._unwatch = self.meta.watch("due", self._on_due_changed)
        self._update_label()

    def on_unmount(self) -> None:
        if self._unwatch is not None:
            self._unwatch()
            self._unwatch = None

    def _on_due_changed(self, node, key, old, new) -> None:
        if self._suppressing:
            return
        self.call_later(self._update_label)

    def _update_label(self) -> None:
        label = self.query_one("#due-label", DueDateLabel)
        due = self.due
        if due:
            text = date_diff(due, date.today())
            label.set_label(text)
            label.set_class(due <= date.today(), "overdue")
            self.set_class(True, "has-due")
        else:
            label.set_label("")
            label.set_class(False, "overdue")
            self.set_class(False, "has-due")

    def _set_due(self, value: date | None) -> None:
        self._suppressing = True
        self.meta.due = value.isoformat() if value else None
        self._suppressing = False
        self._update_label()

    def on_date_button_date_selected(self, event: DateButton.DateSelected) -> None:
        event.stop()
        self._set_due(event.date)

    def on_confirm_button_confirmed(self, event: ConfirmButton.Confirmed) -> None:
        event.stop()
        self._set_due(None)
