"""Tests for the labels editor widgets."""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Button

from ganban.model.loader import _setup_labels
from ganban.ui.labels_editor import (
    AddLabelRow,
    SavedLabelRow,
    UsedLabelRow,
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
        assert len(app.query(SavedLabelRow)) == 0
        assert len(app.query(UsedLabelRow)) == 0
        assert len(app.query(AddLabelRow)) == 1


@pytest.mark.asyncio
async def test_saved_labels_section():
    """Labels with overrides appear in SavedLabelRow."""
    app = LabelsEditorApp(
        card_labels={"001": ["bug"]},
        board_label_overrides={"bug": {"color": "#ff0000"}},
    )
    async with app.run_test():
        saved = app.query(SavedLabelRow)
        assert len(saved) == 1
        assert saved[0].label_name == "bug"
        # No used rows since bug is saved
        assert len(app.query(UsedLabelRow)) == 0


@pytest.mark.asyncio
async def test_used_labels_section():
    """Labels on cards without overrides appear in UsedLabelRow."""
    app = LabelsEditorApp(
        card_labels={"001": ["bug", "feature"]},
        board_label_overrides={},  # No overrides
    )
    async with app.run_test():
        assert len(app.query(SavedLabelRow)) == 0
        used = app.query(UsedLabelRow)
        assert len(used) == 2
        names = {row.label_name for row in used}
        assert names == {"bug", "feature"}


@pytest.mark.asyncio
async def test_mixed_saved_and_used():
    """Mix of saved and used labels shows in correct sections."""
    app = LabelsEditorApp(
        card_labels={"001": ["bug", "feature"]},
        board_label_overrides={"bug": {"color": "#ff0000"}},
    )
    async with app.run_test():
        saved = app.query(SavedLabelRow)
        used = app.query(UsedLabelRow)
        assert len(saved) == 1
        assert saved[0].label_name == "bug"
        assert len(used) == 1
        assert used[0].label_name == "feature"


@pytest.mark.asyncio
async def test_add_label_creates_saved():
    """Adding a new label creates it as saved (with color override)."""
    app = LabelsEditorApp()
    async with app.run_test() as pilot:
        add_row = app.query_one(AddLabelRow)
        add_row.post_message(AddLabelRow.LabelCreated("urgent"))
        await pilot.pause()

        saved = app.query(SavedLabelRow)
        assert len(saved) == 1
        assert saved[0].label_name == "urgent"
        assert "urgent" in app.board.meta.labels.keys()


@pytest.mark.asyncio
async def test_delete_saved_removes_override_only():
    """Deleting a saved label removes override but keeps label on cards."""
    app = LabelsEditorApp(
        card_labels={"001": ["bug"]},
        board_label_overrides={"bug": {"color": "#ff0000"}},
    )
    async with app.run_test() as pilot:
        row = app.query_one(SavedLabelRow)
        row.post_message(SavedLabelRow.DeleteRequested("bug"))
        await pilot.pause()

        # Override is gone
        assert app.board.meta.labels.bug is None
        # But card still has the label
        assert "bug" in app.board.cards["001"].meta.labels


@pytest.mark.asyncio
async def test_delete_used_removes_from_cards():
    """Deleting a used label removes it from all cards."""
    app = LabelsEditorApp(
        card_labels={"001": ["bug"]},
    )
    async with app.run_test() as pilot:
        row = app.query_one(UsedLabelRow)
        row.post_message(UsedLabelRow.DeleteRequested("bug"))
        await pilot.pause()

        # Label is gone from card
        assert app.board.cards["001"].meta.labels is None


@pytest.mark.asyncio
async def test_save_used_label():
    """Saving a used label promotes it to saved with computed color."""
    app = LabelsEditorApp(
        card_labels={"001": ["bug"]},
    )
    async with app.run_test() as pilot:
        row = app.query_one(UsedLabelRow)
        row.post_message(UsedLabelRow.SaveRequested("bug"))
        await pilot.pause()

        # Now has override
        assert app.board.meta.labels.bug is not None
        assert app.board.meta.labels.bug.color is not None


@pytest.mark.asyncio
async def test_rename_saved_label():
    """Renaming a saved label updates cards and override."""
    app = LabelsEditorApp(
        card_labels={"001": ["bug"]},
        board_label_overrides={"bug": {"color": "#ff0000"}},
    )
    async with app.run_test() as pilot:
        row = app.query_one(SavedLabelRow)
        row.post_message(SavedLabelRow.NameRenamed("bug", "defect"))
        await pilot.pause()

        assert app.board.cards["001"].meta.labels == ["defect"]


@pytest.mark.asyncio
async def test_color_change():
    """Changing color updates the override."""
    app = LabelsEditorApp(
        card_labels={"001": ["bug"]},
        board_label_overrides={"bug": {"color": "#ff0000"}},
    )
    async with app.run_test() as pilot:
        row = app.query_one(SavedLabelRow)
        row.post_message(SavedLabelRow.ColorChanged("bug", "#00ff00"))
        await pilot.pause()

        assert app.board.meta.labels.bug.color == "#00ff00"
