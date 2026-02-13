"""Reusable inline tag widget with edit and delete."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.css.query import NoMatches
from textual.events import DescendantBlur
from textual.message import Message
from textual.widgets import Input, Static

from ganban.ui.search import SearchInput


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
            yield Static("×", classes="tag-delete")

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
