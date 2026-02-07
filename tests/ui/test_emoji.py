"""Tests for the emoji picker."""

import pytest
from textual.app import App, ComposeResult

from ganban.ui.emoji import (
    DEFAULT_EMOJIS,
    EmojiButton,
    build_emoji_menu,
    emoji_for_email,
    parse_committer,
)
from ganban.ui.menu import ContextMenu, MenuItem, MenuRow


# --- Sync tests (no app needed) ---


def test_build_emoji_menu_structure():
    """Menu has 6 rows of 5 items each."""
    rows = build_emoji_menu()
    assert len(rows) == 6
    assert all(isinstance(r, MenuRow) for r in rows)
    for row in rows:
        assert len(row._items) == 5


def test_build_emoji_menu_clear_item():
    """First item in first row is the clear button with id 'none'."""
    rows = build_emoji_menu()
    assert rows[0]._items[0].item_id == "none"
    assert rows[0]._items[0].label == "🧑"


def test_build_emoji_menu_has_29_emojis():
    """Grid has 29 emoji items (30 cells minus 1 clear)."""
    rows = build_emoji_menu()
    emoji_items = [item for row in rows for item in row._items if item.item_id != "none"]
    assert len(emoji_items) == 29


def test_build_emoji_menu_ids_are_emojis():
    """Each non-clear item's item_id is the emoji itself."""
    rows = build_emoji_menu()
    for row in rows:
        for item in row._items:
            if item.item_id != "none":
                assert item.item_id == str(item.label)


# --- Committer parsing tests ---


def test_emoji_for_email_is_deterministic():
    """Same email always gives the same emoji."""
    assert emoji_for_email("test@example.com") == emoji_for_email("test@example.com")


def test_emoji_for_email_party_hat():
    """The author gets a party hat. This is rigged and we're proud of it."""
    assert emoji_for_email("gaz@bitplane.net") == "🥳"
    assert emoji_for_email("garethdavidson@gmail.com") == "🥳"


def test_emoji_for_email_picks_from_defaults():
    """Result is always one of the default emojis."""
    for addr in ["a@b.com", "foo@bar.org", "x@y.z"]:
        assert emoji_for_email(addr) in DEFAULT_EMOJIS


def test_parse_committer_name_email():
    """Parses 'Name <email>' format."""
    emoji, name, email = parse_committer("Alice <alice@example.com>")
    assert name == "Alice"
    assert email == "alice@example.com"
    assert emoji in DEFAULT_EMOJIS


def test_parse_committer_full_name():
    """Parses 'First Last <email>' format."""
    emoji, name, email = parse_committer("Bob Smith <bob@example.com>")
    assert name == "Bob Smith"
    assert email == "bob@example.com"


def test_parse_committer_no_angle_brackets():
    """Falls back to full string when no angle brackets."""
    emoji, name, email = parse_committer("just-a-string")
    assert name == "just-a-string"
    assert email == "just-a-string"


def test_parse_committer_strips_whitespace():
    """Handles leading/trailing whitespace."""
    emoji, name, email = parse_committer("  Alice <alice@example.com>  ")
    assert name == "Alice"
    assert email == "alice@example.com"


# --- Async tests ---


class EmojiButtonApp(App):
    """Minimal app for testing the emoji button."""

    def __init__(self, emoji: str | None = None):
        super().__init__()
        self._emoji = emoji
        self.selected_emoji = ...  # sentinel

    def compose(self) -> ComposeResult:
        yield EmojiButton(emoji=self._emoji)

    def on_emoji_button_emoji_selected(self, event: EmojiButton.EmojiSelected) -> None:
        self.selected_emoji = event.emoji


@pytest.mark.asyncio
async def test_emoji_button_displays_default():
    """Button shows the default emoji."""
    app = EmojiButtonApp()
    async with app.run_test():
        btn = app.query_one(EmojiButton)
        assert btn.content == "🧑"


@pytest.mark.asyncio
async def test_emoji_button_displays_custom():
    """Button shows the custom emoji passed in."""
    app = EmojiButtonApp(emoji="🐱")
    async with app.run_test():
        btn = app.query_one(EmojiButton)
        assert btn.content == "🐱"


@pytest.mark.asyncio
async def test_click_opens_menu():
    """Clicking the button opens a ContextMenu."""
    app = EmojiButtonApp()
    async with app.run_test() as pilot:
        btn = app.query_one(EmojiButton)
        await pilot.click(btn)
        assert isinstance(app.screen, ContextMenu)


@pytest.mark.asyncio
async def test_selecting_emoji_emits_message():
    """Clicking an emoji emits EmojiSelected with the emoji string."""
    app = EmojiButtonApp()
    async with app.run_test() as pilot:
        btn = app.query_one(EmojiButton)
        await pilot.click(btn)

        # Pick the second item in the first row (🤵)
        items = list(app.screen.query(MenuItem))
        target = [i for i in items if i.item_id != "none"][0]
        await pilot.click(target)

        assert app.selected_emoji == target.item_id


@pytest.mark.asyncio
async def test_selecting_clear_emits_none():
    """Clicking the clear item emits EmojiSelected(None)."""
    app = EmojiButtonApp()
    async with app.run_test() as pilot:
        btn = app.query_one(EmojiButton)
        await pilot.click(btn)

        clear_item = None
        for item in app.screen.query(MenuItem):
            if item.item_id == "none":
                clear_item = item
                break
        assert clear_item is not None

        await pilot.click(clear_item)
        assert app.selected_emoji is None


@pytest.mark.asyncio
async def test_escape_dismisses():
    """Pressing escape closes the menu without emitting a message."""
    app = EmojiButtonApp()
    async with app.run_test() as pilot:
        btn = app.query_one(EmojiButton)
        await pilot.click(btn)
        assert isinstance(app.screen, ContextMenu)

        await pilot.press("escape")
        assert not isinstance(app.screen, ContextMenu)
        assert app.selected_emoji is ...
