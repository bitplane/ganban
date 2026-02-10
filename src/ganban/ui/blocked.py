"""Blocked toggle widget for card detail screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Static

from ganban.model.node import Node
from ganban.ui.watcher import NodeWatcherMixin

ICON_UNBLOCKED = "\U0001f3ed"
ICON_BLOCKED = "\U0001f6a7"


class BlockedWidget(NodeWatcherMixin, Container):
    """Inline blocked toggle that reads and writes ``meta.blocked``.

    Shows 🚧 when blocked, 🏭 when not. Click to toggle.
    """

    DEFAULT_CSS = """
    BlockedWidget {
        width: auto;
        height: 1;
    }
    BlockedWidget .blocked-toggle {
        width: auto;
        height: 1;
    }
    BlockedWidget .blocked-toggle:hover {
        background: $primary-darken-2;
    }
    """

    def __init__(self, meta: Node, **kwargs) -> None:
        self._init_watcher()
        super().__init__(**kwargs)
        self.meta = meta

    def compose(self) -> ComposeResult:
        icon = ICON_BLOCKED if self.meta.blocked else ICON_UNBLOCKED
        yield Static(icon, classes="blocked-toggle")

    def on_mount(self) -> None:
        self.node_watch(self.meta, "blocked", self._on_blocked_changed)
        self._update_display()

    def _on_blocked_changed(self, node, key, old, new) -> None:
        self.call_later(self._update_display)

    def _update_display(self) -> None:
        toggle = self.query_one(".blocked-toggle", Static)
        if self.meta.blocked:
            toggle.update(ICON_BLOCKED)
            toggle.tooltip = "Blocked"
        else:
            toggle.update(ICON_UNBLOCKED)
            toggle.tooltip = "Not blocked"

    def on_click(self, event) -> None:
        event.stop()
        with self.suppressing():
            self.meta.blocked = True if not self.meta.blocked else None
        self._update_display()
