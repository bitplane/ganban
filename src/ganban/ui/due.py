"""Due date widget with inline editing."""

from __future__ import annotations

from datetime import date

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Static

from ganban.model.node import Node
from ganban.ui.cal import DateButton, date_diff
from ganban.ui.constants import ICON_CALENDAR
from ganban.ui.watcher import NodeWatcherMixin


class DueDateWidget(NodeWatcherMixin, Container):
    """Inline due date display with calendar picker.

    Reads and writes ``meta.due`` on the given Node directly,
    and watches the node so external changes (e.g. the meta editor)
    are reflected immediately.
    """

    def __init__(self, meta: Node, **kwargs) -> None:
        self._init_watcher()
        super().__init__(**kwargs)
        self.meta = meta

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
            yield Static("", classes="due-text")

    def on_mount(self) -> None:
        self.node_watch(self.meta, "due", self._on_due_changed)
        self._update_label()

    def _on_due_changed(self, node, key, old, new) -> None:
        self.call_later(self._update_label)

    def _update_label(self) -> None:
        label = self.query_one(".due-text", Static)
        due = self.due
        if due:
            label.update(date_diff(due, date.today()))
            label.set_class(due <= date.today(), "overdue")
        else:
            label.update("")
            label.set_class(False, "overdue")

    def _set_due(self, value: date | None) -> None:
        with self.suppressing():
            self.meta.due = value.isoformat() if value else None
        self._update_label()

    def on_date_button_date_selected(self, event: DateButton.DateSelected) -> None:
        event.stop()
        self._set_due(event.date)
