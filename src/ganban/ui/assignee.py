"""Assignee widget with user picker."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.events import DescendantBlur
from textual.message import Message
from textual.widgets import Input, OptionList, Static

from ganban.model.node import Node
from ganban.ui.constants import ICON_PERSON
from ganban.ui.emoji import emoji_for_email, parse_committer, resolve_email_display
from ganban.ui.search import SearchInput
from ganban.ui.watcher import NodeWatcherMixin


def resolve_assignee(assigned: str, board: Node) -> tuple[str, str, str]:
    """Parse an assigned string and resolve against board users.

    Returns (emoji, display_name, email). Board users override the
    name and emoji from the parsed committer string.
    """
    _, parsed_name, email = parse_committer(assigned)
    committers = board.git.committers if board.git else None
    committers = committers if isinstance(committers, list) else None
    result = resolve_email_display(email, board.meta, committers)
    if result:
        return result[0], result[1], email
    return emoji_for_email(email), parsed_name, email


def build_assignee_options(board: Node) -> list[tuple[str, str]]:
    """Build options for the assignee SearchInput from board users and git committers.

    Returns (label, value) tuples where label includes emoji and value is the
    committer string.
    """
    options: list[tuple[str, str]] = []
    seen: set[str] = set()

    users = board.meta.users if board.meta else None
    if users is not None:
        for name, user_node in users.items():
            emails = user_node.emails
            if not isinstance(emails, list) or not emails:
                continue
            primary = emails[0]
            committer = f"{name} <{primary}>"
            emoji = user_node.emoji if user_node.emoji else emoji_for_email(primary)
            options.append((f"{emoji} {committer}", committer))
            seen.update(emails)

    committers = board.git.committers if board.git else None
    if isinstance(committers, list):
        for committer_str in committers:
            emoji, name, email = parse_committer(committer_str)
            if email not in seen:
                options.append((f"{emoji} {committer_str}", committer_str))
                seen.add(email)

    return options


class AssigneeWidget(NodeWatcherMixin, Container):
    """Inline assignee display with user picker.

    Reads and writes ``meta.assigned`` on the given card meta Node,
    and watches the node so external changes are reflected immediately.
    """

    class AssigneeSelected(Message):
        def __init__(self, assigned: str | None) -> None:
            super().__init__()
            self.assigned = assigned

    def __init__(self, meta: Node, board: Node, **kwargs) -> None:
        self._init_watcher()
        super().__init__(**kwargs)
        self.meta = meta
        self.board = board

    def compose(self) -> ComposeResult:
        assigned = self.meta.assigned
        if assigned:
            emoji, _, _ = resolve_assignee(assigned, self.board)
        else:
            emoji = ICON_PERSON
        with Horizontal(id="assignee-bar"):
            yield Static(emoji, id="assignee-picker")
            yield Static("", classes="assignee-name")
            yield SearchInput([], placeholder="email@address", id="assignee-search")

    def on_mount(self) -> None:
        self.node_watch(self.meta, "assigned", self._on_assigned_changed)
        self._update_label()

    def _on_assigned_changed(self, source_node: Any, key: str, old: Any, new: Any) -> None:
        self.call_later(self._update_label)

    def _update_label(self) -> None:
        label = self.query_one(".assignee-name", Static)
        picker = self.query_one("#assignee-picker", Static)
        assigned = self.meta.assigned
        if assigned:
            emoji, name, _ = resolve_assignee(assigned, self.board)
            picker.update(emoji)
            label.update(name)
        else:
            picker.update(ICON_PERSON)
            label.update("")

    def _set_assigned(self, value: str | None) -> None:
        with self.suppressing():
            self.meta.assigned = value
        self._update_label()

    def _enter_edit_mode(self) -> None:
        self.add_class("-editing")
        search = self.query_one("#assignee-search", SearchInput)
        search.set_options(build_assignee_options(self.board))
        inp = search.query_one("Input")
        inp.value = self.meta.assigned or ""
        inp.focus()

    def _exit_edit_mode(self) -> None:
        self.remove_class("-editing")
        self._update_label()

    def on_click(self, event) -> None:
        event.stop()
        if not self.has_class("-editing"):
            self._enter_edit_mode()

    def on_search_input_submitted(self, event: SearchInput.Submitted) -> None:
        event.stop()
        if event.value:
            self._set_assigned(event.value)
        elif event.text.strip():
            self._set_assigned(event.text.strip())
        else:
            self._set_assigned(None)
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

    def on_input_changed(self, event: Input.Changed) -> None:
        event.stop()
        picker = self.query_one("#assignee-picker", Static)
        text = event.value.strip()
        if text:
            emoji, _, _ = resolve_assignee(text, self.board)
            picker.update(emoji)
        else:
            picker.update(ICON_PERSON)

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        event.stop()
        picker = self.query_one("#assignee-picker", Static)
        if event.option and event.option.id:
            _, _, email = parse_committer(event.option.id)
            emoji, _, _ = resolve_assignee(event.option.id, self.board)
            picker.update(emoji)
