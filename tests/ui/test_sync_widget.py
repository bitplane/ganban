"""Tests for sync widget icon logic."""

import pytest
from textual.app import App

from ganban.model.node import Node
from ganban.ui.constants import (
    ICON_SYNC_ACTIVE,
    ICON_SYNC_CONFLICT,
    ICON_SYNC_IDLE,
    ICON_SYNC_PAUSED,
)
from ganban.ui.menu import MenuItem
from ganban.ui.sync_widget import SyncWidget, _current_icon


def _make_state(status="idle", local=True, remote=True):
    sync = Node(status=status)
    config = Node(sync_local=local, sync_remote=remote, sync_interval=30)
    return sync, config  # _current_icon takes the ganban section node directly


def test_idle_icon():
    assert _current_icon(*_make_state("idle")) == ICON_SYNC_IDLE


def test_paused_icon():
    assert _current_icon(*_make_state("idle", local=False, remote=False)) == ICON_SYNC_PAUSED


def test_conflict_icon():
    assert _current_icon(*_make_state("conflict")) == ICON_SYNC_CONFLICT


def test_error_icon():
    assert _current_icon(*_make_state("error")) == ICON_SYNC_CONFLICT


def test_paused_overrides_error():
    assert _current_icon(*_make_state("error", local=False, remote=False)) == ICON_SYNC_PAUSED


@pytest.mark.asyncio
async def test_pause_and_dismiss_error():
    sync, config = _make_state("error")
    sync.error = "Push rejected"
    board = Node(git=Node(sync=sync, config=Node(ganban=config)))
    app = App()
    async with app.run_test() as pilot:
        widget = SyncWidget(board)
        await app.mount(widget)
        assert widget.tooltip == "Push rejected"
        widget._on_menu_closed(MenuItem("Local", "toggle_local"))
        widget._on_menu_closed(MenuItem("Remote", "toggle_remote"))
        await pilot.pause()
        assert widget.tooltip is None
        widget._show_menu(0, 0)
        await pilot.pause()
        dismiss = next(item for item in app.screen.query(MenuItem) if item.item_id == "dismiss_error")
        dismiss.post_message(MenuItem.Clicked(dismiss))
        await pilot.pause()
        assert sync.status == "idle"
        assert sync.error is None


def test_pull_icon():
    assert _current_icon(*_make_state("pull")) == ICON_SYNC_ACTIVE


def test_load_icon():
    assert _current_icon(*_make_state("load")) == ICON_SYNC_ACTIVE


def test_save_icon():
    assert _current_icon(*_make_state("save")) == ICON_SYNC_ACTIVE


def test_push_icon():
    assert _current_icon(*_make_state("push")) == ICON_SYNC_ACTIVE


def test_conflict_overrides_paused():
    """Conflict status takes priority even when both toggles are off."""
    assert _current_icon(*_make_state("conflict", local=False, remote=False)) == ICON_SYNC_CONFLICT
