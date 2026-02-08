"""Done toggle widget for card detail screen."""

from __future__ import annotations

from datetime import date

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Static

from ganban.model.node import Node
from ganban.ui.constants import ICON_CHECKED, ICON_UNCHECKED
from ganban.ui.watcher import NodeWatcherMixin


class DoneWidget(NodeWatcherMixin, Container):
    """Inline done toggle that reads and writes ``meta.done``.

    Shows ✅ when done, ⬜ when not. Click to toggle.
    Watches the node so external changes (e.g. the meta editor or context
    menu) are reflected immediately.
    """

    DEFAULT_CSS = """
    DoneWidget {
        width: auto;
        height: 1;
    }
    DoneWidget .done-toggle {
        width: auto;
        height: 1;
        padding: 0 1 0 0;
    }
    DoneWidget .done-toggle:hover {
        background: $primary-darken-2;
    }
    """

    def __init__(self, meta: Node, **kwargs) -> None:
        self._init_watcher()
        super().__init__(**kwargs)
        self.meta = meta

    def compose(self) -> ComposeResult:
        icon = ICON_CHECKED if self.meta.done else ICON_UNCHECKED
        yield Static(icon, classes="done-toggle")

    def on_mount(self) -> None:
        self.node_watch(self.meta, "done", self._on_done_changed)
        self._update_display()

    def _on_done_changed(self, node, key, old, new) -> None:
        self.call_later(self._update_display)

    def _update_display(self) -> None:
        toggle = self.query_one(".done-toggle", Static)
        if self.meta.done:
            toggle.update(ICON_CHECKED)
            toggle.tooltip = self.meta.done
        else:
            toggle.update(ICON_UNCHECKED)
            toggle.tooltip = "Not done"

    def on_click(self, event) -> None:
        event.stop()
        with self.suppressing():
            self.meta.done = date.today().isoformat() if not self.meta.done else None
        self._update_display()
