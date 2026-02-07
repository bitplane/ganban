"""Emoji picker widget."""

from __future__ import annotations

import hashlib
import re

from textual.message import Message
from textual.widgets import Static

from ganban.ui.menu import ContextMenu, MenuItem, MenuRow

EMOJIS: list[list[str]] = [
    ["🧑", "🤵", "👳", "👲", "🫅"],
    ["🤦", "🤷", "💁", "🙋", "🙆"],
    ["🚣", "🏄", "🏊", "🛀", "🧖"],
    ["🤸", "🤺", "🤹", "🧘", "⛹️"],
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


def build_emoji_menu() -> list[MenuRow]:
    """Build a 6x5 emoji picker grid with clear in place of first cell."""
    rows: list[MenuRow] = []
    for row_idx, emoji_row in enumerate(EMOJIS):
        items: list[MenuItem] = []
        for col_idx, emoji in enumerate(emoji_row):
            if row_idx == 0 and col_idx == 0:
                items.append(MenuItem("🧑", item_id="none"))
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

    def __init__(self, emoji: str | None = None, **kwargs) -> None:
        super().__init__(emoji or "🧑", **kwargs)
        self._emoji = emoji

    def on_click(self, event) -> None:
        event.stop()
        menu = ContextMenu(build_emoji_menu(), event.screen_x, event.screen_y)
        self.app.push_screen(menu, self._on_menu_closed)

    def _on_menu_closed(self, item: MenuItem | None) -> None:
        if item is None:
            return
        emoji = None if item.item_id == "none" else item.item_id
        self._emoji = emoji
        self.update(emoji or "🧑")
        self.post_message(self.EmojiSelected(emoji))
