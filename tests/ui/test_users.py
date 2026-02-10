"""Tests for the users editor widgets."""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Button

from ganban.model.node import Node
from ganban.ui.emoji import EmojiButton, emoji_for_email
from ganban.ui.users import (
    AddUserRow,
    EmailTag,
    UsersEditor,
    UserRow,
)


class UsersEditorApp(App):
    """Test app wrapping a UsersEditor."""

    def __init__(self, users=None, committers=None):
        super().__init__()
        meta = {"users": users} if users else {}
        self.meta = Node(**meta)
        self.board = Node(meta=self.meta, git=Node(committers=committers or []))

    def compose(self) -> ComposeResult:
        yield Button("focus target", id="focus-target")
        yield UsersEditor(self.board)


# --- Sync tests for EmojiButton defaults ---


def test_emoji_button_with_custom():
    btn = EmojiButton("🤖", email="alice@example.com")
    assert btn._emoji == "🤖"


def test_emoji_button_default_from_email():
    btn = EmojiButton(email="alice@example.com")
    assert btn._emoji is None
    assert btn._default_emoji == emoji_for_email("alice@example.com")


def test_emoji_button_no_email():
    btn = EmojiButton()
    assert btn._default_emoji == "🙂"


# --- Async tests ---


@pytest.mark.asyncio
async def test_empty_shows_add_row():
    app = UsersEditorApp()
    async with app.run_test():
        assert len(app.query(UserRow)) == 0
        assert len(app.query(AddUserRow)) == 1


@pytest.mark.asyncio
async def test_renders_user_rows():
    app = UsersEditorApp(
        {
            "Alice": {"emoji": "🥳", "emails": ["alice@example.com"]},
            "Bob": {"emoji": "🤖", "emails": ["bob@example.com"]},
        }
    )
    async with app.run_test():
        rows = app.query(UserRow)
        assert len(rows) == 2
        names = {row.user_name for row in rows}
        assert names == {"Alice", "Bob"}


@pytest.mark.asyncio
async def test_add_user():
    app = UsersEditorApp()
    async with app.run_test() as pilot:
        add_row = app.query_one(AddUserRow)
        add_row.post_message(AddUserRow.UserCreated("Alice"))
        await pilot.pause()

        rows = app.query(UserRow)
        assert len(rows) == 1
        assert rows[0].user_name == "Alice"
        assert "Alice" in app.meta.users.keys()


@pytest.mark.asyncio
async def test_add_user_with_name():
    app = UsersEditorApp({"Bob": {"emails": []}})
    async with app.run_test() as pilot:
        add_row = app.query_one(AddUserRow)
        add_row.post_message(AddUserRow.UserCreated("Charlie"))
        await pilot.pause()

        names = set(app.meta.users.keys())
        assert "Bob" in names
        assert "Charlie" in names


@pytest.mark.asyncio
async def test_delete_user():
    app = UsersEditorApp(
        {
            "Alice": {"emails": ["alice@example.com"]},
        }
    )
    async with app.run_test() as pilot:
        row = app.query_one(UserRow)
        row.post_message(UserRow.DeleteRequested("Alice"))
        await pilot.pause()

        assert len(app.query(UserRow)) == 0
        assert "Alice" not in app.meta.users.keys()


@pytest.mark.asyncio
async def test_rename_user():
    app = UsersEditorApp(
        {
            "Alice": {"emails": ["alice@example.com"]},
        }
    )
    async with app.run_test() as pilot:
        row = app.query_one(UserRow)
        row.post_message(UserRow.NameRenamed("Alice", "Alicia"))
        await pilot.pause()

        assert "Alicia" in app.meta.users.keys()
        assert "Alice" not in app.meta.users.keys()


@pytest.mark.asyncio
async def test_emoji_change():
    app = UsersEditorApp(
        {
            "Alice": {"emails": ["alice@example.com"]},
        }
    )
    async with app.run_test() as pilot:
        row = app.query_one(UserRow)
        row.post_message(UserRow.EmojiChanged("Alice", "😈"))
        await pilot.pause()

        assert app.meta.users.Alice.emoji == "😈"


@pytest.mark.asyncio
async def test_add_email():
    app = UsersEditorApp(
        {
            "Alice": {"emails": ["alice@example.com"]},
        }
    )
    async with app.run_test() as pilot:
        row = app.query_one(UserRow)
        row.post_message(UserRow.EmailsChanged("Alice", ["alice@example.com", "alice@work.com"]))
        await pilot.pause()

        assert app.meta.users.Alice.emails == ["alice@example.com", "alice@work.com"]


@pytest.mark.asyncio
async def test_delete_email():
    app = UsersEditorApp(
        {
            "Alice": {"emails": ["alice@example.com", "alice@work.com"]},
        }
    )
    async with app.run_test() as pilot:
        row = app.query_one(UserRow)
        row.post_message(UserRow.EmailsChanged("Alice", ["alice@work.com"]))
        await pilot.pause()

        assert app.meta.users.Alice.emails == ["alice@work.com"]


@pytest.mark.asyncio
async def test_edit_email():
    app = UsersEditorApp(
        {
            "Alice": {"emails": ["alice@example.com"]},
        }
    )
    async with app.run_test() as pilot:
        row = app.query_one(UserRow)
        row.post_message(UserRow.EmailsChanged("Alice", ["alice@newdomain.com"]))
        await pilot.pause()

        assert app.meta.users.Alice.emails == ["alice@newdomain.com"]


@pytest.mark.asyncio
async def test_empty_email_deletes():
    app = UsersEditorApp(
        {
            "Alice": {"emails": ["alice@example.com", "alice@work.com"]},
        }
    )
    async with app.run_test() as pilot:
        row = app.query_one(UserRow)
        tags = list(row.query(EmailTag))
        assert len(tags) == 2
        tags[0].post_message(EmailTag.ValueChanged(0, ""))
        await pilot.pause()

        assert app.meta.users.Alice.emails == ["alice@work.com"]
