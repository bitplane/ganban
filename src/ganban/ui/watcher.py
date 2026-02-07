"""Mixin that manages Node watches with suppression and auto-cleanup."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from ganban.model.node import Callback, ListNode, Node


class NodeWatcherMixin:
    """Mixin for widgets that watch Node keys.

    Subclasses should:
    - Call ``_init_watcher()`` in ``__init__``
    - Use ``self.node_watch(node, key, callback)`` instead of ``node.watch(...)``
    - Use ``with self.suppressing():`` around model writes
    - Skip writing ``on_unmount`` -- the mixin handles cleanup
    """

    def _init_watcher(self) -> None:
        self._watches: list[tuple[Node | ListNode, str, Callback]] = []
        self._suppressing = False

    def node_watch(self, node: Node | ListNode, key: str, callback: Callback) -> None:
        """Register a watch that is auto-guarded by suppression and auto-cleaned on unmount."""

        def guarded(source_node: Any, key: str, old: Any, new: Any) -> None:
            if not self._suppressing:
                callback(source_node, key, old, new)

        unwatch = node.watch(key, guarded)
        self._watches.append(unwatch)

    @contextmanager
    def suppressing(self):
        """Context manager that suppresses watch callbacks for model writes."""
        self._suppressing = True
        try:
            yield
        finally:
            self._suppressing = False

    def on_unmount(self) -> None:
        for unwatch in self._watches:
            unwatch()
        self._watches.clear()
