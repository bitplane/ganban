"""Tests for sync widget icon logic."""

from ganban.model.node import Node
from ganban.ui.constants import (
    ICON_SYNC_ACTIVE,
    ICON_SYNC_CONFLICT,
    ICON_SYNC_IDLE,
    ICON_SYNC_PAUSED,
)
from ganban.ui.sync_widget import _current_icon


def _make_state(status="idle", local=True, remote=True):
    sync = Node(status=status)
    config = Node(sync_local=local, sync_remote=remote, sync_interval=30)
    return sync, config


def test_idle_icon():
    assert _current_icon(*_make_state("idle")) == ICON_SYNC_IDLE


def test_paused_icon():
    assert _current_icon(*_make_state("idle", local=False, remote=False)) == ICON_SYNC_PAUSED


def test_conflict_icon():
    assert _current_icon(*_make_state("conflict")) == ICON_SYNC_CONFLICT


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
