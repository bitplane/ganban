"""Tests for the labels editor widgets."""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Button

from ganban.model.loader import _setup_labels
from ganban.ui.labels_editor import (
    AddLabelRow,
    LabelRow,
    LabelsEditor,
)


class LabelsEditorApp(App):
    """Test app wrapping a LabelsEditor."""

    CSS_PATH = []

    def __init__(self, card_labels=None, board_label_overrides=None):
        super().__init__()
        from tests.model.conftest import _make_board, _make_card, _make_column

        cards = {}
        for card_id, labels in (card_labels or {}).items():
            cards[card_id] = _make_card(f"Card {card_id}", meta={"labels": labels})

        meta = {}
        if board_label_overrides:
            meta["labels"] = board_label_overrides

        self.board = _make_board(
            "/tmp/fake",
            columns=[_make_column("1", "Backlog", links=list(cards.keys()))],
            cards=cards,
            meta=meta,
        )
        _setup_labels(self.board)

    def compose(self) -> ComposeResult:
        yield Button("focus target", id="focus-target")
        yield LabelsEditor(self.board)


@pytest.mark.asyncio
async def test_empty_shows_add_row():
    app = LabelsEditorApp()
    async with app.run_test():
        assert len(app.query(LabelRow)) == 0
        assert len(app.query(AddLabelRow)) == 1


@pytest.mark.asyncio
async def test_renders_label_rows():
    app = LabelsEditorApp(
        card_labels={"001": ["bug", "feature"]},
        board_label_overrides={"bug": {"color": "#ff0000"}},
    )
    async with app.run_test():
        rows = app.query(LabelRow)
        assert len(rows) == 2
        names = {row.label_name for row in rows}
        assert names == {"bug", "feature"}


@pytest.mark.asyncio
async def test_add_label():
    app = LabelsEditorApp()
    async with app.run_test() as pilot:
        add_row = app.query_one(AddLabelRow)
        add_row.post_message(AddLabelRow.LabelCreated("urgent"))
        await pilot.pause()

        rows = app.query(LabelRow)
        assert len(rows) == 1
        assert rows[0].label_name == "urgent"
        assert "urgent" in app.board.meta.labels.keys()


@pytest.mark.asyncio
async def test_delete_label():
    app = LabelsEditorApp(
        card_labels={"001": ["bug"]},
        board_label_overrides={"bug": {"color": "#ff0000"}},
    )
    async with app.run_test() as pilot:
        row = app.query_one(LabelRow)
        row.post_message(LabelRow.DeleteRequested("bug"))
        await pilot.pause()

        assert len(app.query(LabelRow)) == 0
        assert app.board.cards["001"].meta.labels is None


@pytest.mark.asyncio
async def test_rename_label():
    app = LabelsEditorApp(
        card_labels={"001": ["bug"]},
        board_label_overrides={"bug": {"color": "#ff0000"}},
    )
    async with app.run_test() as pilot:
        row = app.query_one(LabelRow)
        row.post_message(LabelRow.NameRenamed("bug", "defect"))
        await pilot.pause()

        assert app.board.cards["001"].meta.labels == ["defect"]


@pytest.mark.asyncio
async def test_color_change():
    app = LabelsEditorApp(
        card_labels={"001": ["bug"]},
        board_label_overrides={"bug": {"color": "#ff0000"}},
    )
    async with app.run_test() as pilot:
        row = app.query_one(LabelRow)
        row.post_message(LabelRow.ColorChanged("bug", "#00ff00"))
        await pilot.pause()

        assert app.board.meta.labels.bug.color == "#00ff00"
