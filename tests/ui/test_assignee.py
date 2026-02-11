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
    AssigneeWidget .assignee-name { width: auto; height: 1; }
    AssigneeWidget #assignee-picker { width: 2; height: 1; }
    AssigneeWidget #assignee-search { display: none; width: 40; }
    AssigneeWidget.-editing #assignee-search { display: block; }
    AssigneeWidget.-editing .assignee-name { display: none; }
    AssigneeWidget #assignee-search Input { height: 1; border: none; padding: 0; }
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
        name_widget = app.query_one(".assignee-name", Static)
        assert name_widget.content == "Alice"


@pytest.mark.asyncio
async def test_shows_default_when_unassigned():
    app = AssigneeApp()
    async with app.run_test():
        picker = app.query_one("#assignee-picker", Static)
        assert picker.content == ICON_PERSON
        name_widget = app.query_one(".assignee-name", Static)
        assert name_widget.content == ""


@pytest.mark.asyncio
async def test_select_assignee_via_search():
    app = AssigneeApp(committers=["Alice <alice@example.com>"])
    async with app.run_test() as pilot:
        widget = app.query_one(AssigneeWidget)
        search = widget.query_one("#assignee-search", SearchInput)

        # Simulate submission
        search.post_message(SearchInput.Submitted("🤖 Alice <alice@example.com>", "Alice <alice@example.com>"))
        await pilot.pause()

        assert app.card_meta.assigned == "Alice <alice@example.com>"


@pytest.mark.asyncio
async def test_unassign_via_empty_submit():
    app = AssigneeApp(assigned="Alice <alice@example.com>")
    async with app.run_test() as pilot:
        widget = app.query_one(AssigneeWidget)
        search = widget.query_one("#assignee-search", SearchInput)

        # Empty submit means unassign
        search.post_message(SearchInput.Submitted("", None))
        await pilot.pause()

        assert app.card_meta.assigned is None
        name_widget = app.query_one(".assignee-name", Static)
        assert name_widget.content == ""


@pytest.mark.asyncio
async def test_free_text_assignee():
    app = AssigneeApp()
    async with app.run_test() as pilot:
        widget = app.query_one(AssigneeWidget)
        search = widget.query_one("#assignee-search", SearchInput)

        # Free text (no matching option)
        search.post_message(SearchInput.Submitted("newuser@example.com", None))
        await pilot.pause()

        assert app.card_meta.assigned == "newuser@example.com"


@pytest.mark.asyncio
async def test_cancel_leaves_unchanged():
    app = AssigneeApp(assigned="Alice <alice@example.com>")
    async with app.run_test() as pilot:
        widget = app.query_one(AssigneeWidget)
        search = widget.query_one("#assignee-search", SearchInput)

        search.post_message(SearchInput.Cancelled())
        await pilot.pause()

        assert app.card_meta.assigned == "Alice <alice@example.com>"


@pytest.mark.asyncio
async def test_reacts_to_external_change():
    app = AssigneeApp()
    async with app.run_test() as pilot:
        name_widget = app.query_one(".assignee-name", Static)
        assert name_widget.content == ""

        app.card_meta.assigned = "Bob <bob@example.com>"
        await pilot.pause()

        assert name_widget.content == "Bob"


@pytest.mark.asyncio
async def test_edit_mode_toggle():
    app = AssigneeApp(committers=["Alice <alice@example.com>"])
    async with app.run_test() as pilot:
        widget = app.query_one(AssigneeWidget)

        assert not widget.has_class("-editing")

        # Enter edit mode
        widget._enter_edit_mode()
        await pilot.pause()
        assert widget.has_class("-editing")

        # Exit edit mode
        widget._exit_edit_mode()
        await pilot.pause()
        assert not widget.has_class("-editing")


@pytest.mark.asyncio
async def test_edit_mode_prepopulates_current_assignee():
    app = AssigneeApp(assigned="user@email.whatever")
    async with app.run_test() as pilot:
        widget = app.query_one(AssigneeWidget)
        widget._enter_edit_mode()
        await pilot.pause()

        inp = widget.query_one("#assignee-search", SearchInput).query_one("Input")
        assert inp.value == "user@email.whatever"


@pytest.mark.asyncio
async def test_edit_mode_input_empty_when_unassigned():
    app = AssigneeApp()
    async with app.run_test() as pilot:
        widget = app.query_one(AssigneeWidget)
        widget._enter_edit_mode()
        await pilot.pause()

        inp = widget.query_one("#assignee-search", SearchInput).query_one("Input")
        assert inp.value == ""


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
        option_list = widget.query_one("#assignee-search", SearchInput).query_one("OptionList")
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
        inp = widget.query_one("#assignee-search", SearchInput).query_one(Input)

        assert picker.content == ICON_PERSON

        # Simulate typing an email
        inp.value = "test@example.com"
        await pilot.pause()

        assert picker.content == emoji_for_email("test@example.com")

        # Clearing the input restores the default icon
        inp.value = ""
        await pilot.pause()

        assert picker.content == ICON_PERSON
