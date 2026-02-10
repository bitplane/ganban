"""Emoji picker widget."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from textual.message import Message
from textual.widgets import Static

from ganban.model.node import Node
from ganban.ui.menu import ContextMenu, MenuItem, MenuRow
from ganban.ui.watcher import NodeWatcherMixin

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


def find_user_by_email(email: str, meta: Node | None) -> tuple[str, Node] | None:
    """Find the (user_name, user_node) for an email in meta.users."""
    users = meta.users if meta else None
    if users is None:
        return None
    for user_name, user_node in users.items():
        emails = user_node.emails
        if isinstance(emails, list) and email in emails:
            return user_name, user_node
    return None


def resolve_email_display(
    email: str,
    meta: Node | None = None,
    committers: list[str] | None = None,
) -> tuple[str, str] | None:
    """Resolve an email to (emoji, display_name).

    Checks meta.users first (custom emoji + user name), then
    git committers (hash emoji + committer name). Returns None
    if the email isn't found in either source.
    """
    result = find_user_by_email(email, meta)
    if result:
        name, user_node = result
        emoji = user_node.emoji or emoji_for_email(email)
        return emoji, name
    if committers:
        for committer_str in committers:
            _, cname, cemail = parse_committer(committer_str)
            if cemail == email:
                return emoji_for_email(email), cname
    return None


def resolve_email_emoji(email: str, meta: Node) -> str:
    """Look up the emoji for an email from meta.users, falling back to hash."""
    result = resolve_email_display(email, meta)
    if result:
        return result[0]
    return emoji_for_email(email)


class EmailEmoji(NodeWatcherMixin, Static):
    """Display-only emoji resolved from an email address.

    Watches meta.users so it updates when custom emojis change.
    """

    def __init__(self, email: str, meta: Node, **kwargs) -> None:
        self._email = email
        self._meta = meta
        self._init_watcher()
        super().__init__(resolve_email_emoji(email, meta), **kwargs)

    def on_mount(self) -> None:
        self.node_watch(self._meta, "users", self._on_users_changed)

    def _on_users_changed(self, source_node: Any, key: str, old: Any, new: Any) -> None:
        self.update(resolve_email_emoji(self._email, self._meta))
