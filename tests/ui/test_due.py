"""Tests for the due date widget."""

from datetime import date, timedelta

import pytest
from textual.app import App, ComposeResult

from ganban.ui.cal import Calendar, CalendarDay
from ganban.ui.due import DueDateLabel, DueDateWidget
from ganban.ui.menu import ContextMenu


class DueDateApp(App):
    """Minimal app for testing due date widget."""

    def __init__(self, due: date | None = None):
        super().__init__()
        self._due = due
        self.due_changed: date | None = ...  # sentinel to distinguish None from not-set

    def compose(self) -> ComposeResult:
        yield DueDateWidget(due=self._due)

    def on_due_date_widget_changed(self, event: DueDateWidget.Changed) -> None:
        self.due_changed = event.due


@pytest.mark.asyncio
async def test_no_due_shows_only_calendar():
    """Widget with no due date shows only calendar button, label empty, delete hidden."""
    app = DueDateApp()
    async with app.run_test():
        widget = app.query_one(DueDateWidget)
        label = widget.query_one("#due-label", DueDateLabel)

        assert label.content == ""
        assert "has-due" not in widget.classes


@pytest.mark.asyncio
async def test_due_shows_label():
    """Widget with due date shows date_diff label."""
    due = date.today() + timedelta(days=5)
    app = DueDateApp(due=due)
    async with app.run_test():
        widget = app.query_one(DueDateWidget)
        label = widget.query_one("#due-label", DueDateLabel)

        assert label.content == "5d"


@pytest.mark.asyncio
async def test_overdue_is_red():
    """Past due date has 'overdue' class."""
    due = date.today() - timedelta(days=3)
    app = DueDateApp(due=due)
    async with app.run_test():
        widget = app.query_one(DueDateWidget)
        label = widget.query_one("#due-label", DueDateLabel)

        assert label.content == "-3d"
        assert "overdue" in label.classes


@pytest.mark.asyncio
async def test_due_today_is_overdue():
    """Due date of today has 'overdue' class."""
    due = date.today()
    app = DueDateApp(due=due)
    async with app.run_test():
        widget = app.query_one(DueDateWidget)
        label = widget.query_one("#due-label", DueDateLabel)

        assert label.content == "0d"
        assert "overdue" in label.classes


@pytest.mark.asyncio
async def test_future_not_overdue():
    """Future due date does not have 'overdue' class."""
    due = date.today() + timedelta(days=1)
    app = DueDateApp(due=due)
    async with app.run_test():
        widget = app.query_one(DueDateWidget)
        label = widget.query_one("#due-label", DueDateLabel)

        assert "overdue" not in label.classes


@pytest.mark.asyncio
async def test_delete_clears_due():
    """Confirming delete clears the due date."""
    due = date.today() + timedelta(days=5)
    app = DueDateApp(due=due)
    async with app.run_test() as pilot:
        widget = app.query_one(DueDateWidget)
        label = widget.query_one("#due-label", DueDateLabel)

        label.post_message(DueDateLabel.Confirmed())
        await pilot.pause()

        assert widget.due is None
        assert app.due_changed is None
        assert label.content == ""


@pytest.mark.asyncio
async def test_hover_shows_delete_icon():
    """Hovering over the due label swaps text for delete icon."""
    due = date.today() + timedelta(days=5)
    app = DueDateApp(due=due)
    async with app.run_test() as pilot:
        widget = app.query_one(DueDateWidget)
        label = widget.query_one("#due-label", DueDateLabel)

        assert label.content == "5d"

        await pilot.hover(DueDateLabel)
        assert label.content == "🚫"

        # Move mouse away - label restores
        await pilot.hover(DueDateWidget, offset=(0, 0))
        assert label.content == "5d"


@pytest.mark.asyncio
async def test_hover_no_due_no_icon():
    """Hovering when no due date doesn't show delete icon."""
    app = DueDateApp()
    async with app.run_test() as pilot:
        widget = app.query_one(DueDateWidget)
        label = widget.query_one("#due-label", DueDateLabel)

        await pilot.hover(DueDateLabel)
        assert label.content == ""


@pytest.mark.asyncio
async def test_calendar_sets_due():
    """Selecting date from calendar sets due date."""
    app = DueDateApp()
    async with app.run_test() as pilot:
        widget = app.query_one(DueDateWidget)
        picker = widget.query_one("#due-picker")

        # Click date button to open calendar
        await pilot.click(picker)
        assert isinstance(app.screen, ContextMenu)

        # Click a day in the calendar
        cal = app.screen.query_one(Calendar)
        target_day = None
        for day in cal.query(CalendarDay):
            if day.date.month == date.today().month:
                target_day = day
                break
        assert target_day is not None

        await pilot.click(target_day)

        # Due should be set
        assert widget.due == target_day.date
        assert app.due_changed == target_day.date


@pytest.mark.asyncio
async def test_changing_due_updates_label():
    """Selecting a new date updates the label."""
    due = date.today() + timedelta(days=5)
    app = DueDateApp(due=due)
    async with app.run_test() as pilot:
        widget = app.query_one(DueDateWidget)
        label = widget.query_one("#due-label", DueDateLabel)
        assert label.content == "5d"

        picker = widget.query_one("#due-picker")
        await pilot.click(picker)

        # Click a day 10 days from today
        cal = app.screen.query_one(Calendar)
        target_date = date.today() + timedelta(days=10)
        target_day = None
        for day in cal.query(CalendarDay):
            if day.date == target_date:
                target_day = day
                break

        if target_day:
            await pilot.click(target_day)
            assert label.content == "10d"


@pytest.mark.asyncio
async def test_due_property():
    """Widget exposes due date via property."""
    due = date(2026, 6, 15)
    app = DueDateApp(due=due)
    async with app.run_test():
        widget = app.query_one(DueDateWidget)
        assert widget.due == due


@pytest.mark.asyncio
async def test_no_has_due_class_when_no_due():
    """Widget without due date does not have 'has-due' class."""
    app = DueDateApp()
    async with app.run_test():
        widget = app.query_one(DueDateWidget)
        assert "has-due" not in widget.classes


@pytest.mark.asyncio
async def test_has_due_class_when_due():
    """Widget with due date has 'has-due' class."""
    due = date.today() + timedelta(days=5)
    app = DueDateApp(due=due)
    async with app.run_test():
        widget = app.query_one(DueDateWidget)
        assert "has-due" in widget.classes
