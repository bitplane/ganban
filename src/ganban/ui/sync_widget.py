"""Sync status indicator widget for the board header."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Static

from ganban.model.node import Node
from ganban.ui.constants import (
    ICON_SYNC_ACTIVE,
    ICON_SYNC_CONFLICT,
    ICON_SYNC_IDLE,
    ICON_SYNC_PAUSED,
)
from ganban.ui.menu import ContextMenu, MenuItem, MenuSeparator
from ganban.ui.watcher import NodeWatcherMixin

INTERVAL_PRESETS = [
    (10, "10s"),
    (30, "30s"),
    (60, "1m"),
    (120, "2m"),
    (300, "5m"),
]


def _current_icon(sync: Node | None, config: Node | None) -> str:
    """Return the icon for the current sync state."""
    if sync is None:
        return ICON_SYNC_IDLE
    if sync.status == "conflict":
        return ICON_SYNC_CONFLICT
    if config and not config.sync_local and not config.sync_remote:
        return ICON_SYNC_PAUSED
    if sync.status and sync.status != "idle":
        return ICON_SYNC_ACTIVE
    return ICON_SYNC_IDLE


class SyncWidget(NodeWatcherMixin, Container):
    """Sync status indicator. Shows current sync state as an emoji.

    Click to open a context menu with local/remote toggles and interval presets.
    """

    def __init__(self, board: Node, **kwargs) -> None:
        self._init_watcher()
        super().__init__(**kwargs)
        self.board = board

    def compose(self) -> ComposeResult:
        icon = _current_icon(self.board.git.sync, self.board.git.config.ganban)
        yield Static(icon, classes="sync-icon")

    def on_mount(self) -> None:
        self.node_watch(self.board.git.sync, "status", self._on_sync_changed)
        for key in ("sync_local", "sync_remote"):
            self.node_watch(self.board.git.config.ganban, key, self._on_sync_changed)
        self._update_display()

    def _on_sync_changed(self, node, key, old, new) -> None:
        self.call_later(self._update_display)

    def _update_display(self) -> None:
        icon_widget = self.query_one(".sync-icon", Static)
        icon = _current_icon(self.board.git.sync, self.board.git.config.ganban)
        icon_widget.update(icon)

    def on_click(self, event) -> None:
        event.stop()
        self._show_menu(event.screen_x, event.screen_y)

    def _show_menu(self, x: int, y: int) -> None:
        config = self.board.git.config.ganban
        sync = self.board.git.sync
        local_check = "☑" if config.sync_local else "☐"
        remote_check = "☑" if config.sync_remote else "☐"
        current_time = config.sync_interval or 30

        items = [
            MenuItem(f"{local_check} Local sync", "toggle_local"),
            MenuItem(f"{remote_check} Remote sync", "toggle_remote"),
            MenuSeparator(),
        ]

        for seconds, label in INTERVAL_PRESETS:
            bullet = "● " if seconds == current_time else "○ "
            items.append(MenuItem(f"{bullet}{label}", f"interval_{seconds}"))

        if sync.status == "conflict":
            items.append(MenuSeparator())
            items.append(MenuItem("Dismiss conflict", "dismiss_conflict"))

        self.app.push_screen(ContextMenu(items, x, y), self._on_menu_closed)

    def _on_menu_closed(self, item: MenuItem | None) -> None:
        if item is None:
            return
        config = self.board.git.config.ganban
        sync = self.board.git.sync
        with self.suppressing():
            if item.item_id == "toggle_local":
                config.sync_local = not config.sync_local
            elif item.item_id == "toggle_remote":
                config.sync_remote = not config.sync_remote
            elif item.item_id == "dismiss_conflict":
                sync.status = "idle"
            elif item.item_id and item.item_id.startswith("interval_"):
                config.sync_interval = int(item.item_id.split("_")[1])
        self._update_display()
