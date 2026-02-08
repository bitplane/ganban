"""Tests for sync widget icon logic."""

from ganban.model.node import Node
from ganban.ui.constants import (
    ICON_SYNC_ACTIVE,
    ICON_SYNC_CONFLICT,
    ICON_SYNC_IDLE,
    ICON_SYNC_PAUSED,
)
from ganban.ui.sync_widget import _current_icon


def _make_sync(status="idle", local=True, remote=True):
    return Node(status=status, local=local, remote=remote, time=30)


def test_idle_icon():
    assert _current_icon(_make_sync("idle")) == ICON_SYNC_IDLE


def test_paused_icon():
    assert _current_icon(_make_sync("idle", local=False, remote=False)) == ICON_SYNC_PAUSED


def test_conflict_icon():
    assert _current_icon(_make_sync("conflict")) == ICON_SYNC_CONFLICT


def test_pull_icon():
    assert _current_icon(_make_sync("pull")) == ICON_SYNC_ACTIVE


def test_load_icon():
    assert _current_icon(_make_sync("load")) == ICON_SYNC_ACTIVE


def test_save_icon():
    assert _current_icon(_make_sync("save")) == ICON_SYNC_ACTIVE


def test_push_icon():
    assert _current_icon(_make_sync("push")) == ICON_SYNC_ACTIVE


def test_conflict_overrides_paused():
    """Conflict status takes priority even when both toggles are off."""
    assert _current_icon(_make_sync("conflict", local=False, remote=False)) == ICON_SYNC_CONFLICT
