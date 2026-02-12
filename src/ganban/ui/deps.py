"""Dependency editor widget for card detail bar."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.events import DescendantBlur
from textual.widgets import Input, Static

from ganban.model.node import Node
from ganban.parser import first_title
from ganban.ui.search import SearchInput
from ganban.ui.watcher import NodeWatcherMixin

ICON_DEPS = "\U0001f517"  # 🔗


def build_dep_options(board: Node, card_id: str, current_deps: list[str]) -> list[tuple[str, str]]:
    """Build (label, value) options for the dep search dropdown.

    Returns non-archived cards excluding the current card and cards already
    in the deps list.
    """
    exclude = {card_id} | set(current_deps)
    options: list[tuple[str, str]] = []
    for cid, card in board.cards.items():
        if cid in exclude or card.archived:
            continue
        title = first_title(card.sections) if card.sections else cid
        options.append((f"{cid} {title}", cid))
    return options


class DepsWidget(NodeWatcherMixin, Container):
    """Inline deps editor for card detail bar.

    Displays dep IDs next to a link icon. Click the icon to add a dep,
    click an ID to replace it. Uses SearchInput for card selection.
    """

    def __init__(self, meta: Node, board: Node, card_id: str, **kwargs) -> None:
        self._init_watcher()
        super().__init__(**kwargs)
        self.meta = meta
        self.board = board
        self.card_id = card_id
        self._editing_index: int | None = None  # None = adding, int = replacing

    def compose(self) -> ComposeResult:
        with Horizontal(id="deps-bar"):
            yield Static(ICON_DEPS, id="deps-add")
            yield Horizontal(id="deps-ids")
            yield SearchInput([], placeholder="card id", id="deps-search")

    def on_mount(self) -> None:
        self.node_watch(self.meta, "deps", self._on_deps_changed)
        self._rebuild_ids()

    def _on_deps_changed(self, source_node: Any, key: str, old: Any, new: Any) -> None:
        self.call_later(self._rebuild_ids)

    def _rebuild_ids(self) -> None:
        """Clear and rebuild the dep ID Static widgets."""
        container = self.query_one("#deps-ids", Horizontal)
        for child in list(container.children):
            child.remove()
        deps = self.meta.deps
        if deps and isinstance(deps, list):
            for dep_id in deps:
                container.mount(Static(str(dep_id), classes="dep-id"))

    def _enter_edit_mode(self, index: int | None = None) -> None:
        """Enter edit mode. index=None means adding, int means replacing."""
        self._editing_index = index
        self.add_class("-editing")
        current_deps = list(self.meta.deps or [])
        if index is not None and index < len(current_deps):
            filter_deps = current_deps[:index] + current_deps[index + 1 :]
        else:
            filter_deps = current_deps
        search = self.query_one("#deps-search", SearchInput)
        search.set_options(build_dep_options(self.board, self.card_id, filter_deps))
        inp = search.query_one(Input)
        inp.value = ""
        inp.focus()

    def _exit_edit_mode(self) -> None:
        self._editing_index = None
        search = self.query_one("#deps-search", SearchInput)
        search._close_dropdown()
        self.remove_class("-editing")
        self._rebuild_ids()
        self.screen.focus()

    def on_click(self, event) -> None:
        event.stop()
        if self.has_class("-editing"):
            return
        target = event.widget
        if target.id == "deps-add":
            self._enter_edit_mode()
        elif target.has_class("dep-id"):
            container = self.query_one("#deps-ids", Horizontal)
            idx = list(container.children).index(target)
            self._enter_edit_mode(index=idx)

    def on_search_input_submitted(self, event: SearchInput.Submitted) -> None:
        event.stop()
        dep_id = event.value
        if not dep_id:
            text = event.text.strip()
            if text and text in self.board.cards:
                dep_id = text
        deps = list(self.meta.deps or [])
        if dep_id:
            if self._editing_index is not None and self._editing_index < len(deps):
                deps[self._editing_index] = dep_id
            else:
                deps.append(dep_id)
        elif self._editing_index is not None and self._editing_index < len(deps):
            del deps[self._editing_index]
        else:
            self._exit_edit_mode()
            return
        with self.suppressing():
            self.meta.deps = deps or None
        self._exit_edit_mode()

    def on_search_input_cancelled(self, event: SearchInput.Cancelled) -> None:
        event.stop()
        self._exit_edit_mode()

    def on_descendant_blur(self, event: DescendantBlur) -> None:
        if self.has_class("-editing"):
            self.call_after_refresh(self._maybe_exit_on_blur)

    def _maybe_exit_on_blur(self) -> None:
        focused = self.app.focused
        if focused is None or focused not in self.walk_children():
            self._exit_edit_mode()
