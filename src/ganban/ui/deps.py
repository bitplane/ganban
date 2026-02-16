"""Dependency editor widget for card detail bar."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Static

from ganban.model.node import Node
from ganban.parser import first_title
from ganban.ui.tag import Tag
from ganban.ui.watcher import NodeWatcherMixin

ICON_DEPS = "\U0001f517"  # 🔗


def build_card_options(board: Node, exclude_id: str = "") -> list[tuple[str, str]]:
    """Build (label, value) options for card references.

    Returns all non-archived cards (optionally excluding one by ID).
    The label is ``"ID Title"`` and the value is the card ID.
    """
    options: list[tuple[str, str]] = []
    for cid, card in board.cards.items():
        if cid == exclude_id or card.archived:
            continue
        title = first_title(card.sections) if card.sections else cid
        options.append((f"{cid} {title}", cid))
    return options


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
    click a tag to edit it, click × to delete. Uses Tag widgets with
    SearchInput for card selection.
    """

    def __init__(self, meta: Node, board: Node, card_id: str, **kwargs) -> None:
        self._init_watcher()
        super().__init__(**kwargs)
        self.meta = meta
        self.board = board
        self.card_id = card_id

    def compose(self) -> ComposeResult:
        with Horizontal(id="deps-bar"):
            yield Static(ICON_DEPS, id="deps-add")
            yield Horizontal(id="deps-tags")

    def on_mount(self) -> None:
        self.node_watch(self.meta, "deps", self._on_deps_changed)
        self._rebuild_tags()

    def _on_deps_changed(self, source_node: Any, key: str, old: Any, new: Any) -> None:
        self.call_later(self._rebuild_tags)

    def _rebuild_tags(self) -> None:
        """Clear and rebuild the dep tag widgets."""
        container = self.query_one("#deps-tags", Horizontal)
        for child in list(container.children):
            child.remove()
        deps = self.meta.deps
        if deps and isinstance(deps, list):
            for dep_id in deps:
                container.mount(Tag(value=str(dep_id)))

    def _current_deps_except(self, exclude_tag: Tag | None = None) -> list[str]:
        """Get current deps, optionally excluding one tag's value."""
        deps = list(self.meta.deps or [])
        if exclude_tag is not None:
            tags = list(self.query_one("#deps-tags", Horizontal).query(Tag))
            idx = tags.index(exclude_tag) if exclude_tag in tags else None
            if idx is not None and idx < len(deps):
                return deps[:idx] + deps[idx + 1 :]
        return deps

    def on_click(self, event) -> None:
        event.stop()
        target = event.widget
        if target.id == "deps-add":
            self._add_new_tag()
        elif target.has_class("tag-label"):
            tag = target.parent.parent  # tag-label → tag-row → Tag
            if isinstance(tag, Tag) and not tag.has_class("-editing"):
                options = build_dep_options(self.board, self.card_id, self._current_deps_except(tag))
                tag.start_editing(options)

    def _add_new_tag(self) -> None:
        """Mount a temporary blank tag for adding a new dep."""
        container = self.query_one("#deps-tags", Horizontal)
        tag = Tag(value="", classes="-new")
        container.mount(tag)
        options = build_dep_options(self.board, self.card_id, self._current_deps_except())
        tag.start_editing(options)

    def on_tag_changed(self, event: Tag.Changed) -> None:
        event.stop()
        tag = event.tag
        new_id = event.new_value
        # validate that it's actually a card
        if new_id not in self.board.cards:
            if tag.has_class("-new"):
                tag.remove()
            return

        deps = list(self.meta.deps or [])
        tags = list(self.query_one("#deps-tags", Horizontal).query(Tag))
        idx = tags.index(tag) if tag in tags else None

        if tag.has_class("-new"):
            tag.remove_class("-new")
            deps.append(new_id)
        elif idx is not None and idx < len(deps):
            deps[idx] = new_id

        tag.update_display(str(new_id))
        with self.suppressing():
            self.meta.deps = deps or None

    def on_tag_deleted(self, event: Tag.Deleted) -> None:
        event.stop()
        tag = event.tag
        deps = list(self.meta.deps or [])
        tags = list(self.query_one("#deps-tags", Horizontal).query(Tag))
        idx = tags.index(tag) if tag in tags else None

        if tag.has_class("-new"):
            tag.remove()
            return

        if idx is not None and idx < len(deps):
            del deps[idx]
        tag.remove()
        with self.suppressing():
            self.meta.deps = deps or None
