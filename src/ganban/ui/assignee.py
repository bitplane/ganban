"""Assignee widget with user picker."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.message import Message
from textual.widgets import Static

from ganban.model.node import Node
from ganban.ui.constants import ICON_PERSON
from ganban.ui.emoji import emoji_for_email, parse_committer, resolve_email_display
from ganban.ui.menu import ContextMenu, MenuItem, MenuSeparator
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


def build_assignee_menu(board: Node) -> list[MenuItem | MenuSeparator]:
    """Build a menu of assignable users from board.meta.users and git committers."""
    items: list[MenuItem | MenuSeparator] = [
        MenuItem("Unassigned", item_id="unassign"),
        MenuSeparator(),
    ]
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
            items.append(MenuItem(f"{emoji} {committer}", item_id=committer))
            seen.update(emails)

    committers = board.git.committers if board.git else None
    if isinstance(committers, list):
        for committer_str in committers:
            emoji, name, email = parse_committer(committer_str)
            if email not in seen:
                items.append(MenuItem(f"{emoji} {committer_str}", item_id=committer_str))
                seen.add(email)

    return items


class AssigneeButton(Static):
    """Button that opens the assignee picker menu."""

    class AssigneeSelected(Message):
        def __init__(self, assigned: str | None) -> None:
            super().__init__()
            self.assigned = assigned

    DEFAULT_CSS = """
    AssigneeButton { width: 2; height: 1; }
    AssigneeButton:hover { background: $primary-darken-2; }
    """

    def __init__(self, board: Node, emoji: str = ICON_PERSON, **kwargs) -> None:
        super().__init__(emoji, **kwargs)
        self._board = board

    def on_click(self, event) -> None:
        event.stop()
        items = build_assignee_menu(self._board)
        menu = ContextMenu(items, event.screen_x, event.screen_y)
        self.app.push_screen(menu, self._on_menu_closed)

    def _on_menu_closed(self, item: MenuItem | None) -> None:
        if item is None:
            return
        if item.item_id == "unassign":
            self.post_message(self.AssigneeSelected(None))
        else:
            self.post_message(self.AssigneeSelected(item.item_id))


class AssigneeWidget(NodeWatcherMixin, Container):
    """Inline assignee display with user picker.

    Reads and writes ``meta.assigned`` on the given card meta Node,
    and watches the node so external changes are reflected immediately.
    """

    DEFAULT_CSS = """
    AssigneeWidget {
        width: auto;
        height: 1;
    }
    AssigneeWidget > Horizontal {
        width: auto;
        height: 1;
    }
    AssigneeWidget .assignee-name {
        width: auto;
        height: 1;
    }
    """

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
        with Horizontal():
            yield AssigneeButton(self.board, emoji=emoji, id="assignee-picker")
            yield Static("", classes="assignee-name")

    def on_mount(self) -> None:
        self.node_watch(self.meta, "assigned", self._on_assigned_changed)
        self._update_label()

    def _on_assigned_changed(self, source_node: Any, key: str, old: Any, new: Any) -> None:
        self.call_later(self._update_label)

    def _update_label(self) -> None:
        label = self.query_one(".assignee-name", Static)
        picker = self.query_one("#assignee-picker", AssigneeButton)
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

    def on_assignee_button_assignee_selected(self, event: AssigneeButton.AssigneeSelected) -> None:
        event.stop()
        self._set_assigned(event.assigned)
