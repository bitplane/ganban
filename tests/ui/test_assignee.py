"""Tests for the assignee widget."""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Button, Static

from ganban.model.node import Node
from ganban.ui.constants import ICON_PERSON
from ganban.ui.assignee import (
    AssigneeButton,
    AssigneeWidget,
    build_assignee_menu,
    resolve_assignee,
)
from ganban.ui.emoji import emoji_for_email


# --- Sync tests for build_assignee_menu ---


def test_menu_from_users():
    board = Node(
        meta={"users": {"Alice": {"emoji": "🤖", "emails": ["alice@example.com"]}}},
        git={"committers": []},
    )
    items = build_assignee_menu(board)
    assert items[0].item_id == "unassign"
    assert items[2].item_id == "Alice <alice@example.com>"
    assert "🤖" in str(items[2].label)
    assert "Alice" in str(items[2].label)


def test_menu_from_committers():
    board = Node(
        meta={},
        git={"committers": ["Bob <bob@example.com>"]},
    )
    items = build_assignee_menu(board)
    assert items[2].item_id == "Bob <bob@example.com>"


def test_menu_deduplicates():
    board = Node(
        meta={"users": {"Alice": {"emails": ["alice@example.com"]}}},
        git={"committers": ["Alice <alice@example.com>"]},
    )
    items = build_assignee_menu(board)
    assert len(items) == 3  # unassign + separator + Alice


def test_menu_deduplicates_secondary_emails():
    board = Node(
        meta={"users": {"Alice": {"emails": ["alice@example.com", "alice@work.com"]}}},
        git={"committers": ["Alice Work <alice@work.com>"]},
    )
    items = build_assignee_menu(board)
    assert len(items) == 3  # unassign + separator + Alice
    assert items[2].item_id == "Alice <alice@example.com>"


def test_menu_empty_board():
    board = Node(meta={}, git={"committers": []})
    items = build_assignee_menu(board)
    assert len(items) == 2  # unassign + separator


# --- Sync tests for resolve_assignee ---


def test_resolve_assignee_from_users():
    board = Node(
        meta={"users": {"Ally": {"emoji": "🤖", "emails": ["alice@example.com"]}}},
        git={"committers": []},
    )
    emoji, name, email = resolve_assignee("Alice <alice@example.com>", board)
    assert emoji == "🤖"
    assert name == "Ally"
    assert email == "alice@example.com"


def test_resolve_assignee_from_committer():
    board = Node(meta={}, git={"committers": []})
    emoji, name, email = resolve_assignee("Bob <bob@example.com>", board)
    assert emoji == emoji_for_email("bob@example.com")
    assert name == "Bob"
    assert email == "bob@example.com"


def test_resolve_assignee_bare_email():
    board = Node(meta={}, git={"committers": []})
    emoji, name, email = resolve_assignee("bob@example.com", board)
    assert email == "bob@example.com"
    assert name == "bob@example.com"


# --- Async tests ---


class AssigneeApp(App):
    def __init__(self, assigned=None, users=None, committers=None):
        super().__init__()
        meta_dict = {}
        if assigned:
            meta_dict["assigned"] = assigned
        self.card_meta = Node(**meta_dict)
        board_meta = {"users": users} if users else {}
        git = {"committers": committers or []}
        self.board = Node(meta=board_meta, git=git)

    def compose(self) -> ComposeResult:
        yield Button("focus target", id="focus-target")
        yield AssigneeWidget(self.card_meta, self.board)


@pytest.mark.asyncio
async def test_shows_emoji_when_assigned():
    app = AssigneeApp(
        assigned="Alice <alice@example.com>",
        users={"Alice": {"emoji": "🤖", "emails": ["alice@example.com"]}},
    )
    async with app.run_test():
        picker = app.query_one(AssigneeButton)
        assert picker.content == "🤖"
        name_widget = app.query_one(".assignee-name", Static)
        assert name_widget.content == "Alice"


@pytest.mark.asyncio
async def test_shows_default_when_unassigned():
    app = AssigneeApp()
    async with app.run_test():
        picker = app.query_one(AssigneeButton)
        assert picker.content == ICON_PERSON
        name_widget = app.query_one(".assignee-name", Static)
        assert name_widget.content == ""


@pytest.mark.asyncio
async def test_select_assignee():
    app = AssigneeApp(committers=["Alice <alice@example.com>"])
    async with app.run_test() as pilot:
        widget = app.query_one(AssigneeWidget)
        widget.on_assignee_button_assignee_selected(AssigneeButton.AssigneeSelected("Alice <alice@example.com>"))
        await pilot.pause()

        assert app.card_meta.assigned == "Alice <alice@example.com>"


@pytest.mark.asyncio
async def test_clear_assignee():
    app = AssigneeApp(assigned="Alice <alice@example.com>")
    async with app.run_test() as pilot:
        widget = app.query_one(AssigneeWidget)
        widget.on_assignee_button_assignee_selected(AssigneeButton.AssigneeSelected(None))
        await pilot.pause()

        assert app.card_meta.assigned is None
        name_widget = app.query_one(".assignee-name", Static)
        assert name_widget.content == ""


@pytest.mark.asyncio
async def test_reacts_to_external_change():
    app = AssigneeApp()
    async with app.run_test() as pilot:
        name_widget = app.query_one(".assignee-name", Static)
        assert name_widget.content == ""

        app.card_meta.assigned = "Bob <bob@example.com>"
        await pilot.pause()

        assert name_widget.content == "Bob"
