"""Tests for the deps widget."""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Button, Static

from ganban.model.node import ListNode, Node
from ganban.ui.deps import DepsWidget, build_dep_options, ICON_DEPS
from ganban.ui.search import SearchInput
from ganban.ui.tag import Tag


# --- Helpers ---


def _make_board(*cards, archived_ids=None):
    """Build a board Node with the given card IDs.

    Each positional arg is a card ID string. Cards get a sections ListNode
    with a single title entry.
    """
    archived_ids = set(archived_ids or [])
    board = Node()
    board.cards = ListNode()
    for cid in cards:
        card = Node()
        card.sections = ListNode()
        card.sections[f"Card {cid}"] = ""
        if cid in archived_ids:
            card.archived = True
        board.cards[cid] = card
    return board


# --- Sync tests for build_dep_options ---


def test_build_dep_options_excludes_current_card():
    board = _make_board("1", "2", "3")
    options = build_dep_options(board, "2", [])
    ids = [v for _, v in options]
    assert "2" not in ids
    assert "1" in ids
    assert "3" in ids


def test_build_dep_options_excludes_archived():
    board = _make_board("1", "2", "3", archived_ids=["3"])
    options = build_dep_options(board, "1", [])
    ids = [v for _, v in options]
    assert "3" not in ids
    assert "2" in ids


def test_build_dep_options_excludes_existing_deps():
    board = _make_board("1", "2", "3")
    options = build_dep_options(board, "1", ["2"])
    ids = [v for _, v in options]
    assert "2" not in ids
    assert "3" in ids


def test_build_dep_options_format():
    board = _make_board("1", "2")
    options = build_dep_options(board, "1", [])
    assert len(options) == 1
    label, value = options[0]
    assert value == "2"
    assert label == "2 Card 2"


# --- Async tests ---


class DepsApp(App):
    CSS = """
    DepsWidget { width: auto; height: 1; }
    DepsWidget > Horizontal { width: auto; height: 1; }
    #deps-tags { width: auto; height: 1; }
    #deps-add { width: 2; height: 1; }
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

    def __init__(self, deps=None, card_ids=None, archived_ids=None):
        super().__init__()
        meta_dict = {}
        if deps is not None:
            meta_dict["deps"] = deps
        self.card_meta = Node(**meta_dict)
        self.board = _make_board(*(card_ids or ["1", "2", "3"]), archived_ids=archived_ids)
        self.card_id = "1"

    def compose(self) -> ComposeResult:
        yield Button("focus target", id="focus-target")
        yield DepsWidget(self.card_meta, self.board, self.card_id)


@pytest.mark.asyncio
async def test_shows_empty_when_no_deps():
    app = DepsApp()
    async with app.run_test():
        icon = app.query_one("#deps-add", Static)
        assert icon.content == ICON_DEPS
        tags = app.query_one("#deps-tags").query(Tag)
        assert len(tags) == 0


@pytest.mark.asyncio
async def test_shows_dep_ids():
    app = DepsApp(deps=["2", "3"])
    async with app.run_test():
        tags = list(app.query_one("#deps-tags").query(Tag))
        assert len(tags) == 2
        assert tags[0].value == "2"
        assert tags[1].value == "3"


@pytest.mark.asyncio
async def test_add_dep_via_tag():
    app = DepsApp(card_ids=["1", "2", "3"])
    async with app.run_test() as pilot:
        widget = app.query_one(DepsWidget)
        widget._add_new_tag()
        await pilot.pause()

        # Find the new tag and simulate search submission
        tags = list(widget.query(Tag))
        new_tag = tags[-1]
        search = new_tag.query_one(SearchInput)
        search.post_message(SearchInput.Submitted("2 Card 2", "2"))
        await pilot.pause()

        assert app.card_meta.deps == ["2"]


@pytest.mark.asyncio
async def test_cancel_leaves_unchanged():
    app = DepsApp(deps=["2"])
    async with app.run_test() as pilot:
        tags = list(app.query_one(DepsWidget).query(Tag))
        tag = tags[0]
        tag.post_message(SearchInput.Cancelled())
        await pilot.pause()

        assert app.card_meta.deps == ["2"]


@pytest.mark.asyncio
async def test_delete_dep_via_tag():
    app = DepsApp(deps=["2", "3"], card_ids=["1", "2", "3"])
    async with app.run_test() as pilot:
        tags = list(app.query_one(DepsWidget).query(Tag))
        assert len(tags) == 2

        tags[0].post_message(Tag.Deleted(tags[0]))
        await pilot.pause()

        assert app.card_meta.deps == ["3"]


@pytest.mark.asyncio
async def test_delete_last_dep_sets_none():
    app = DepsApp(deps=["2"], card_ids=["1", "2"])
    async with app.run_test() as pilot:
        tags = list(app.query_one(DepsWidget).query(Tag))
        tags[0].post_message(Tag.Deleted(tags[0]))
        await pilot.pause()

        assert app.card_meta.deps is None


@pytest.mark.asyncio
async def test_reacts_to_external_change():
    app = DepsApp()
    async with app.run_test() as pilot:
        tags = list(app.query_one("#deps-tags").query(Tag))
        assert len(tags) == 0

        app.card_meta.deps = ["3"]
        await pilot.pause()

        tags = list(app.query_one("#deps-tags").query(Tag))
        assert len(tags) == 1
        assert tags[0].value == "3"


@pytest.mark.asyncio
async def test_add_invalid_card_id_rejected():
    app = DepsApp(card_ids=["1", "2", "3"])
    async with app.run_test() as pilot:
        widget = app.query_one(DepsWidget)
        widget._add_new_tag()
        await pilot.pause()

        tags = list(widget.query(Tag))
        new_tag = tags[-1]
        search = new_tag.query_one(SearchInput)
        search.post_message(SearchInput.Submitted("nonexistent", None))
        await pilot.pause()

        assert app.card_meta.deps is None
