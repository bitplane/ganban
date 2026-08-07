"""Reusable inline tag widget with edit and delete."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.css.query import NoMatches
from textual.events import DescendantBlur
from textual.message import Message
from textual.widgets import Input, Static

from ganban.model.node import Node
from ganban.ui.constants import ICON_DELETE
from ganban.ui.search import SearchInput
from ganban.ui.watcher import NodeWatcherMixin


class Tag(Static):
    """Inline tag: ``[label ×]`` in view mode, ``[SearchInput ×]`` in edit mode.

    Parameters
    ----------
    value:
        Underlying data value (label name, card id, committer string).
    display:
        Rich renderable shown in view mode.  Defaults to *value*.
    """

    class Changed(Message):
        """User submitted a new value for this tag."""

        def __init__(self, tag: Tag, old_value: str, new_value: str) -> None:
            super().__init__()
            self.tag = tag
            self.old_value = old_value
            self.new_value = new_value

    class Deleted(Message):
        """User clicked the × button."""

        def __init__(self, tag: Tag) -> None:
            super().__init__()
            self.tag = tag

    def __init__(
        self,
        value: str,
        display: str | Text | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.value = value
        self._display: str | Text = display if display is not None else value
        self._pending_edit_options: list[tuple[str, str]] | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(classes="tag-row"):
            yield Static(self._display, classes="tag-label")
            yield SearchInput([], classes="tag-search")
            yield Static(ICON_DELETE, classes="tag-delete")

    def on_mount(self) -> None:
        if self._pending_edit_options is not None:
            options = self._pending_edit_options
            self._pending_edit_options = None
            self.start_editing(options)

    def update_display(self, display: str | Text) -> None:
        """Change the rendered label text."""
        self._display = display
        self.query_one(".tag-label", Static).update(display)

    def start_editing(self, options: list[tuple[str, str]]) -> None:
        """Enter edit mode with the given search options.

        If called before the widget is composed, defers until on_mount.
        """
        try:
            search = self.query_one(".tag-search", SearchInput)
        except NoMatches:
            self._pending_edit_options = options
            return
        self.add_class("-editing")
        search.set_options(options)
        inp = search.query_one(Input)
        inp.value = ""
        inp.focus()

    def _exit_edit_mode(self) -> None:
        search = self.query_one(".tag-search", SearchInput)
        search._close_dropdown()
        self.remove_class("-editing")
        if not self.value:
            self.post_message(self.Deleted(self))
            return
        self.query_one(".tag-label", Static).update(self._display)
        self.screen.focus()

    def on_click(self, event) -> None:
        target = event.widget
        if target.has_class("tag-delete"):
            event.stop()
            self.post_message(self.Deleted(self))

    def on_search_input_submitted(self, event: SearchInput.Submitted) -> None:
        event.stop()
        new_value = event.value or event.text.strip()
        if new_value and new_value != self.value:
            old = self.value
            self.value = new_value
            self.post_message(self.Changed(self, old, new_value))
        elif not new_value:
            self.post_message(self.Deleted(self))
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


class TagListWidget(NodeWatcherMixin, Container):
    """Base for inline tag-list editors bound to a list on a meta Node.

    Renders an add icon plus one Tag per value. Subclasses set meta_key,
    icon and the element ids, implement options_for(), and may override
    display_for() and validate().
    """

    meta_key: str = ""
    icon: str = ""
    bar_id: str = ""
    add_id: str = ""
    tags_id: str = ""

    def __init__(self, meta: Node, board: Node, **kwargs) -> None:
        self._init_watcher()
        super().__init__(**kwargs)
        self.meta = meta
        self.board = board

    def display_for(self, value: str):
        """Renderable shown for a value in view mode."""
        return str(value)

    def options_for(self, current: list[str]) -> list[tuple[str, str]]:
        """Dropdown options offered while editing, given the other values."""
        raise NotImplementedError

    def validate(self, value: str) -> bool:
        """Whether a submitted value may be stored."""
        return True

    def compose(self) -> ComposeResult:
        with Horizontal(id=self.bar_id):
            yield Static(self.icon, id=self.add_id)
            yield Horizontal(id=self.tags_id)

    def on_mount(self) -> None:
        self.node_watch(self.meta, self.meta_key, self._on_values_changed)
        self._rebuild_tags()

    def _on_values_changed(self, source_node, key, old, new) -> None:
        self.call_later(self._rebuild_tags)

    def _values(self) -> list:
        values = getattr(self.meta, self.meta_key)
        return list(values) if isinstance(values, list) else []

    def _set_values(self, values: list) -> None:
        with self.suppressing():
            setattr(self.meta, self.meta_key, values or None)

    def _tags(self) -> list[Tag]:
        return list(self.query_one(f"#{self.tags_id}", Horizontal).query(Tag))

    def _rebuild_tags(self) -> None:
        """Clear and rebuild the tag widgets from the meta list."""
        container = self.query_one(f"#{self.tags_id}", Horizontal)
        for child in list(container.children):
            child.remove()
        for value in self._values():
            container.mount(Tag(value=str(value), display=self.display_for(value)))

    def _current_except(self, exclude_tag: Tag | None = None) -> list:
        """Get current values, optionally excluding one tag's value."""
        values = self._values()
        if exclude_tag is not None:
            tags = self._tags()
            idx = tags.index(exclude_tag) if exclude_tag in tags else None
            if idx is not None and idx < len(values):
                return values[:idx] + values[idx + 1 :]
        return values

    def on_click(self, event) -> None:
        event.stop()
        target = event.widget
        if target.id == self.add_id:
            self._add_new_tag()
        elif target.has_class("tag-label"):
            tag = target.parent.parent  # tag-label → tag-row → Tag
            if isinstance(tag, Tag) and not tag.has_class("-editing"):
                tag.start_editing(self.options_for(self._current_except(tag)))

    def _add_new_tag(self) -> None:
        """Mount a temporary blank tag for adding a new value."""
        container = self.query_one(f"#{self.tags_id}", Horizontal)
        tag = Tag(value="", classes="-new")
        container.mount(tag)
        tag.start_editing(self.options_for(self._current_except()))

    def on_tag_changed(self, event: Tag.Changed) -> None:
        event.stop()
        tag = event.tag
        value = event.new_value
        if not self.validate(value):
            if tag.has_class("-new"):
                tag.remove()
            return

        values = self._values()
        tags = self._tags()
        idx = tags.index(tag) if tag in tags else None

        if tag.has_class("-new"):
            tag.remove_class("-new")
            values.append(value)
        elif idx is not None and idx < len(values):
            values[idx] = value

        tag.update_display(self.display_for(value))
        self._set_values(values)

    def on_tag_deleted(self, event: Tag.Deleted) -> None:
        event.stop()
        tag = event.tag
        if tag.has_class("-new"):
            tag.remove()
            return

        values = self._values()
        tags = self._tags()
        idx = tags.index(tag) if tag in tags else None
        if idx is not None and idx < len(values):
            del values[idx]
        tag.remove()
        self._set_values(values)
