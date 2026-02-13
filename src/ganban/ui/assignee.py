"""Assignee widget with user picker."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.message import Message
from textual.widgets import Input, OptionList, Static

from ganban.model.node import Node
from ganban.ui.constants import ICON_PERSON
from ganban.ui.emoji import emoji_for_email, parse_committer, resolve_email_display
from ganban.ui.tag import Tag
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
    Uses a single optional Tag widget for the assigned user.
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
            if assigned:
                _, name, _ = resolve_assignee(assigned, self.board)
                yield Tag(value=assigned, display=name, classes="assignee-tag")

    def on_mount(self) -> None:
        self.node_watch(self.meta, "assigned", self._on_assigned_changed)

    def _on_assigned_changed(self, source_node: Any, key: str, old: Any, new: Any) -> None:
        self.call_later(self._rebuild_tag)

    def _rebuild_tag(self) -> None:
        """Rebuild the assignee tag to match current meta."""
        bar = self.query_one("#assignee-bar", Horizontal)
        for tag in list(bar.query(Tag)):
            tag.remove()
        picker = self.query_one("#assignee-picker", Static)
        assigned = self.meta.assigned
        if assigned:
            emoji, name, _ = resolve_assignee(assigned, self.board)
            picker.update(emoji)
            bar.mount(Tag(value=assigned, display=name, classes="assignee-tag"))
        else:
            picker.update(ICON_PERSON)

    def _update_picker_emoji(self, text: str) -> None:
        """Update the emoji icon based on text being typed."""
        picker = self.query_one("#assignee-picker", Static)
        if text.strip():
            emoji, _, _ = resolve_assignee(text, self.board)
            picker.update(emoji)
        else:
            picker.update(ICON_PERSON)

    def on_click(self, event) -> None:
        event.stop()
        target = event.widget
        # clicking the icon or tag label starts editing
        if target.id == "assignee-picker":
            self._start_editing()
        elif target.has_class("tag-label"):
            tag = target.parent.parent
            if isinstance(tag, Tag) and not tag.has_class("-editing"):
                self._start_editing(tag)

    def _start_editing(self, tag: Tag | None = None) -> None:
        """Start editing — reuse existing tag or create a new one."""
        options = build_assignee_options(self.board)
        if tag is None:
            tags = list(self.query_one("#assignee-bar", Horizontal).query(Tag))
            tag = tags[0] if tags else None
        if tag is None:
            bar = self.query_one("#assignee-bar", Horizontal)
            tag = Tag(value="", classes="assignee-tag -new")
            bar.mount(tag)
        tag.start_editing(options)

    def on_tag_changed(self, event: Tag.Changed) -> None:
        event.stop()
        tag = event.tag
        new_value = event.new_value
        tag.remove_class("-new")
        with self.suppressing():
            self.meta.assigned = new_value
        emoji, name, _ = resolve_assignee(new_value, self.board)
        self.query_one("#assignee-picker", Static).update(emoji)
        tag.value = new_value
        tag.update_display(name)
        self._update_picker_emoji("")

    def on_tag_deleted(self, event: Tag.Deleted) -> None:
        event.stop()
        tag = event.tag
        tag.remove()
        with self.suppressing():
            self.meta.assigned = None
        self.query_one("#assignee-picker", Static).update(ICON_PERSON)

    def on_input_changed(self, event: Input.Changed) -> None:
        event.stop()
        self._update_picker_emoji(event.value)

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        event.stop()
        if event.option and event.option.id:
            self._update_picker_emoji(event.option.id)
