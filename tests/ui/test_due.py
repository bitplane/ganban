"""Tests for the due date widget."""

from datetime import date, timedelta

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from ganban.model.node import Node
from ganban.ui.cal import Calendar, CalendarDay, NavButton
from ganban.ui.due import DueDateWidget
from ganban.ui.menu import ContextMenu


class DueDateApp(App):
    """Minimal app for testing due date widget."""

    def __init__(self, due: date | None = None):
        super().__init__()
        self.meta = Node(due=due.isoformat() if due else None)

    def compose(self) -> ComposeResult:
        yield DueDateWidget(self.meta)


def _label_text(app):
    """Get the due label text content."""
    return app.query_one(".due-text", Static).content


@pytest.mark.asyncio
async def test_no_due_shows_only_calendar():
    """Widget with no due date shows only calendar button, label empty."""
    app = DueDateApp()
    async with app.run_test():
        assert _label_text(app) == ""


@pytest.mark.asyncio
async def test_due_shows_label():
    """Widget with due date shows date_diff label."""
    due = date.today() + timedelta(days=5)
    app = DueDateApp(due=due)
    async with app.run_test():
        assert _label_text(app) == "5d"


@pytest.mark.asyncio
async def test_overdue_has_class():
    """Past due date has 'overdue' class."""
    due = date.today() - timedelta(days=3)
    app = DueDateApp(due=due)
    async with app.run_test():
        label = app.query_one(".due-text", Static)

        assert _label_text(app) == "-3d"
        assert "overdue" in label.classes


@pytest.mark.asyncio
async def test_due_today_is_overdue():
    """Due date of today has 'overdue' class."""
    due = date.today()
    app = DueDateApp(due=due)
    async with app.run_test():
        label = app.query_one(".due-text", Static)

        assert _label_text(app) == "0d"
        assert "overdue" in label.classes


@pytest.mark.asyncio
async def test_future_not_overdue():
    """Future due date does not have 'overdue' class."""
    due = date.today() + timedelta(days=1)
    app = DueDateApp(due=due)
    async with app.run_test():
        label = app.query_one(".due-text", Static)

        assert "overdue" not in label.classes


@pytest.mark.asyncio
async def test_calendar_sets_due():
    """Selecting date from calendar sets due date."""
    app = DueDateApp()
    async with app.run_test() as pilot:
        widget = app.query_one(DueDateWidget)
        picker = widget.query_one("#due-picker")

        await pilot.click(picker)
        assert isinstance(app.screen, ContextMenu)

        cal = app.screen.query_one(Calendar)
        target_day = None
        for day in cal.query(CalendarDay):
            if day.date.month == date.today().month:
                target_day = day
                break
        assert target_day is not None

        await pilot.click(target_day)

        assert widget.due == target_day.date
        assert app.meta.due == target_day.date.isoformat()


@pytest.mark.asyncio
async def test_changing_due_updates_label():
    """Selecting a new date updates the label."""
    due = date.today() + timedelta(days=5)
    app = DueDateApp(due=due)
    async with app.run_test() as pilot:
        assert _label_text(app) == "5d"

        widget = app.query_one(DueDateWidget)
        picker = widget.query_one("#due-picker")
        await pilot.click(picker)

        cal = app.screen.query_one(Calendar)
        target_date = date.today() + timedelta(days=10)
        target_day = None
        for day in cal.query(CalendarDay):
            if day.date == target_date:
                target_day = day
                break

        if target_day:
            await pilot.click(target_day)
            assert _label_text(app) == "10d"


@pytest.mark.asyncio
async def test_due_property():
    """Widget exposes due date via property."""
    due = date(2026, 6, 15)
    app = DueDateApp(due=due)
    async with app.run_test():
        widget = app.query_one(DueDateWidget)
        assert widget.due == due


@pytest.mark.asyncio
async def test_calendar_clear_button_clears_due():
    """Clicking the clear button in the calendar clears the due date."""
    due = date.today() + timedelta(days=5)
    app = DueDateApp(due=due)
    async with app.run_test() as pilot:
        widget = app.query_one(DueDateWidget)
        picker = widget.query_one("#due-picker")

        await pilot.click(picker)
        assert isinstance(app.screen, ContextMenu)

        cal = app.screen.query_one(Calendar)
        clear_btn = cal.query_one("#clear", NavButton)
        await pilot.click(clear_btn)
        await pilot.pause()

        assert widget.due is None
        assert app.meta.due is None
        assert _label_text(app) == ""


@pytest.mark.asyncio
async def test_external_node_change_updates_widget():
    """Changing meta.due externally updates the widget label."""
    app = DueDateApp()
    async with app.run_test() as pilot:
        widget = app.query_one(DueDateWidget)
        assert widget.due is None

        target = date.today() + timedelta(days=7)
        app.meta.due = target.isoformat()
        await pilot.pause()

        assert widget.due == target
        assert _label_text(app) == "7d"
