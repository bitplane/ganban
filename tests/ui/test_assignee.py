"""Tests for the assignee widget."""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Button, Input, Static

from ganban.model.node import Node
from ganban.ui.constants import ICON_PERSON
from ganban.ui.assignee import (
    AssigneeWidget,
    build_assignee_options,
    resolve_assignee,
)
from ganban.ui.emoji import emoji_for_email
from ganban.ui.search import SearchInput
from ganban.ui.tag import Tag


# --- Sync tests for build_assignee_options ---


def test_options_from_users():
    board = Node(
        meta={"users": {"Alice": {"emoji": "🤖", "emails": ["alice@example.com"]}}},
        git={"committers": []},
    )
    options = build_assignee_options(board)
    assert len(options) == 1
    label, value = options[0]
    assert value == "Alice <alice@example.com>"
    assert "🤖" in label
    assert "Alice" in label


def test_options_from_committers():
    board = Node(
        meta={},
        git={"committers": ["Bob <bob@example.com>"]},
    )
    options = build_assignee_options(board)
    assert len(options) == 1
    assert options[0][1] == "Bob <bob@example.com>"


def test_options_deduplicates():
    board = Node(
        meta={"users": {"Alice": {"emails": ["alice@example.com"]}}},
        git={"committers": ["Alice <alice@example.com>"]},
    )
    options = build_assignee_options(board)
    assert len(options) == 1


def test_options_deduplicates_secondary_emails():
    board = Node(
        meta={"users": {"Alice": {"emails": ["alice@example.com", "alice@work.com"]}}},
        git={"committers": ["Alice Work <alice@work.com>"]},
    )
    options = build_assignee_options(board)
    assert len(options) == 1
    assert options[0][1] == "Alice <alice@example.com>"


def test_options_empty_board():
    board = Node(meta={}, git={"committers": []})
    options = build_assignee_options(board)
    assert len(options) == 0


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
    CSS = """
    AssigneeWidget { width: auto; height: 1; }
    AssigneeWidget > Horizontal { width: auto; height: 1; }
    AssigneeWidget #assignee-picker { width: 2; height: 1; }
    Tag { width: auto; height: 1; padding: 0 1 0 0; }
    .tag-row { width: auto; height: 1; }
    .tag-label { width: auto; height: 1; }
    .tag-delete { width: auto; height: 1; }
    Tag .tag-search { display: none; width: 40; }
    Tag.-editing .tag-search { display: block; }
    Tag.-editing .tag-label { display: none; }
    Tag .tag-search Input { height: 1; border: none; padding: 0; }
    SearchInput { width: 100%; height: auto; }
    SearchInput > Input { width: 100%; }
    SearchInput > OptionList {
        width: 100%; max-height: 8; display: none;
        overlay: screen; background: $surface; border: solid $primary;
    }
    SearchInput > OptionList.-visible { display: block; }
    """

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
        picker = app.query_one("#assignee-picker", Static)
        assert picker.content == "🤖"
        tags = list(app.query_one(AssigneeWidget).query(Tag))
        assert len(tags) == 1


@pytest.mark.asyncio
async def test_shows_default_when_unassigned():
    app = AssigneeApp()
    async with app.run_test():
        picker = app.query_one("#assignee-picker", Static)
        assert picker.content == ICON_PERSON
        tags = list(app.query_one(AssigneeWidget).query(Tag))
        assert len(tags) == 0


@pytest.mark.asyncio
async def test_select_assignee_via_tag():
    app = AssigneeApp(committers=["Alice <alice@example.com>"])
    async with app.run_test() as pilot:
        widget = app.query_one(AssigneeWidget)

        # Start editing (creates a new tag)
        widget._start_editing()
        await pilot.pause()

        tag = list(widget.query(Tag))[0]
        tag.post_message(Tag.Changed(tag, "", "Alice <alice@example.com>"))
        await pilot.pause()

        assert app.card_meta.assigned == "Alice <alice@example.com>"


@pytest.mark.asyncio
async def test_unassign_via_tag_delete():
    app = AssigneeApp(assigned="Alice <alice@example.com>")
    async with app.run_test() as pilot:
        widget = app.query_one(AssigneeWidget)
        tags = list(widget.query(Tag))
        assert len(tags) == 1

        tags[0].post_message(Tag.Deleted(tags[0]))
        await pilot.pause()

        assert app.card_meta.assigned is None
        picker = app.query_one("#assignee-picker", Static)
        assert picker.content == ICON_PERSON


@pytest.mark.asyncio
async def test_cancel_leaves_unchanged():
    app = AssigneeApp(assigned="Alice <alice@example.com>")
    async with app.run_test() as pilot:
        widget = app.query_one(AssigneeWidget)
        tags = list(widget.query(Tag))
        tag = tags[0]
        tag.post_message(SearchInput.Cancelled())
        await pilot.pause()

        assert app.card_meta.assigned == "Alice <alice@example.com>"


@pytest.mark.asyncio
async def test_reacts_to_external_change():
    app = AssigneeApp()
    async with app.run_test() as pilot:
        widget = app.query_one(AssigneeWidget)
        tags = list(widget.query(Tag))
        assert len(tags) == 0

        app.card_meta.assigned = "Bob <bob@example.com>"
        await pilot.pause()

        tags = list(widget.query(Tag))
        assert len(tags) == 1


@pytest.mark.asyncio
async def test_live_emoji_preview():
    app = AssigneeApp(
        users={"Alice": {"emoji": "🤖", "emails": ["alice@example.com"]}},
        committers=["Bob <bob@example.com>"],
    )
    async with app.run_test() as pilot:
        widget = app.query_one(AssigneeWidget)
        picker = widget.query_one("#assignee-picker", Static)

        # Simulate option highlighted
        from textual.widgets.option_list import Option

        option = Option("🤖 Alice <alice@example.com>", id="Alice <alice@example.com>")
        # We need an OptionList to create the event — get one from any search
        widget._start_editing()
        await pilot.pause()
        tag = list(widget.query(Tag))[0]
        option_list = tag.query_one(SearchInput).query_one("OptionList")
        event = option_list.OptionHighlighted(option_list, option, 0)
        widget.on_option_list_option_highlighted(event)
        await pilot.pause()

        assert picker.content == "🤖"


@pytest.mark.asyncio
async def test_emoji_updates_live_while_typing():
    app = AssigneeApp()
    async with app.run_test() as pilot:
        widget = app.query_one(AssigneeWidget)
        picker = widget.query_one("#assignee-picker", Static)

        assert picker.content == ICON_PERSON

        # Start editing to get an input
        widget._start_editing()
        await pilot.pause()

        tag = list(widget.query(Tag))[0]
        inp = tag.query_one(SearchInput).query_one(Input)

        inp.value = "test@example.com"
        await pilot.pause()

        assert picker.content == emoji_for_email("test@example.com")

        inp.value = ""
        await pilot.pause()

        assert picker.content == ICON_PERSON
