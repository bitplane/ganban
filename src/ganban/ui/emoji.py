"""Emoji picker widget."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from typing import Any

from textual.message import Message
from textual.widgets import Static

from ganban.model.node import Node
from ganban.ui.menu import ContextMenu, MenuItem, MenuRow

EMOJIS: list[list[str]] = [
    ["🙂", "🧑", "🤵", "👳", "👲"],
    ["🤦", "🤷", "💁", "🙋", "🙆"],
    ["🚣", "🏄", "🏊", "🛀", "🧖"],
    ["🤸", "🤺", "🤹", "🧘", "🫅"],
    ["🌈", "👰", "🧜", "🫄", "🛌"],
    ["🤖", "💀", "😈", "🐶", "🐱"],
]


DEFAULT_EMOJIS = "🥳😄😙😬😆🤓😱😂🙃😊😁😛😏"

_COMMITTER_RE = re.compile(r"^(.+?)\s*<([^>]+)>$")


def emoji_for_email(email: str) -> str:
    """Pick a deterministic default emoji for an email address.

    Uses the last nibble of the md5 digest, modulo 13.
    """
    last_nibble = int(hashlib.md5(email.encode()).hexdigest()[-1], 16)
    return DEFAULT_EMOJIS[last_nibble % len(DEFAULT_EMOJIS)]


def parse_committer(committer: str) -> tuple[str, str, str]:
    """Parse a committer string into (emoji, name, email).

    Accepts "Name <email>" format. If parsing fails, the full
    string is used as both name and email.
    """
    match = _COMMITTER_RE.match(committer.strip())
    if match:
        name, email = match.group(1), match.group(2)
    else:
        name = email = committer.strip()
    return emoji_for_email(email), name, email


def build_emoji_menu(email: str | None = None) -> list[MenuRow]:
    """Build a 6x5 emoji picker grid with default/clear as first cell."""
    default = emoji_for_email(email) if email else EMOJIS[0][0]
    rows: list[MenuRow] = []
    for row_idx, emoji_row in enumerate(EMOJIS):
        items: list[MenuItem] = []
        for col_idx, emoji in enumerate(emoji_row):
            if row_idx == 0 and col_idx == 0:
                items.append(MenuItem(default, item_id="none"))
            else:
                items.append(MenuItem(emoji, item_id=emoji))
        rows.append(MenuRow(*items))
    return rows


class EmojiButton(Static):
    """A button that opens an emoji picker menu."""

    class EmojiSelected(Message):
        """Posted when an emoji is selected."""

        def __init__(self, emoji: str | None) -> None:
            super().__init__()
            self.emoji = emoji

    DEFAULT_CSS = """
    EmojiButton { width: 2; height: 1; }
    EmojiButton:hover { background: $primary-darken-2; }
    """

    def __init__(self, emoji: str | None = None, *, email: str | None = None, **kwargs) -> None:
        self._emoji = emoji
        self._email = email
        super().__init__(emoji or self._default_emoji, **kwargs)

    @property
    def _default_emoji(self) -> str:
        if self._email:
            return emoji_for_email(self._email)
        return "🙂"

    @property
    def email(self) -> str | None:
        return self._email

    @email.setter
    def email(self, value: str | None) -> None:
        self._email = value
        if self._emoji is None:
            self.update(self._default_emoji)

    def on_click(self, event) -> None:
        event.stop()
        menu = ContextMenu(build_emoji_menu(self._email), event.screen_x, event.screen_y)
        self.app.push_screen(menu, self._on_menu_closed)

    def _on_menu_closed(self, item: MenuItem | None) -> None:
        if item is None:
            return
        emoji = None if item.item_id == "none" else item.item_id
        self._emoji = emoji
        self.update(emoji or self._default_emoji)
        self.post_message(self.EmojiSelected(emoji))


def resolve_email_emoji(email: str, meta: Node) -> str:
    """Look up the emoji for an email from meta.users, falling back to hash."""
    users = meta.users
    if users is not None:
        for _, user_node in users.items():
            emails = user_node.emails
            if isinstance(emails, list) and email in emails:
                if user_node.emoji is not None:
                    return user_node.emoji
                break
    return emoji_for_email(email)


class EmailEmoji(Static):
    """Display-only emoji resolved from an email address.

    Watches meta.users so it updates when custom emojis change.
    """

    DEFAULT_CSS = """
    EmailEmoji { width: 2; height: 1; }
    """

    def __init__(self, email: str, meta: Node, **kwargs) -> None:
        self._email = email
        self._meta = meta
        self._unwatch: Callable | None = None
        super().__init__(resolve_email_emoji(email, meta), **kwargs)

    def on_mount(self) -> None:
        self._unwatch = self._meta.watch("users", self._on_users_changed)

    def on_unmount(self) -> None:
        if self._unwatch is not None:
            self._unwatch()
            self._unwatch = None

    def _on_users_changed(self, source_node: Any, key: str, old: Any, new: Any) -> None:
        self.update(resolve_email_emoji(self._email, self._meta))
