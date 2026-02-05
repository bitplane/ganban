"""Tests for the calendar widget."""

from datetime import date

import pytest
from textual.app import App, ComposeResult

from ganban.ui.cal import Calendar, CalendarDay


class CalendarApp(App):
    """Minimal app for testing calendar."""

    def __init__(self, selected: date | None = None):
        super().__init__()
        self._selected = selected
        self.date_selected: date | None = None

    def compose(self) -> ComposeResult:
        yield Calendar(selected=self._selected)

    def on_calendar_date_selected(self, event: Calendar.DateSelected) -> None:
        self.date_selected = event.date


@pytest.fixture
def app():
    return CalendarApp()


@pytest.mark.asyncio
async def test_displays_current_month(app):
    """Calendar displays current month by default."""
    async with app.run_test():
        cal = app.query_one(Calendar)
        title = cal.query_one("#title")
        expected = date.today().strftime("%b %Y")
        assert title.content == expected


@pytest.mark.asyncio
async def test_today_has_css_class(app):
    """Today's date has 'today' CSS class."""
    async with app.run_test():
        cal = app.query_one(Calendar)
        today = date.today()
        for day in cal.query(CalendarDay):
            if day.date == today:
                assert "today" in day.classes
                return
        pytest.fail("Today's date not found in calendar")


@pytest.mark.asyncio
async def test_click_day_selects():
    """Clicking day selects it and emits DateSelected."""
    app = CalendarApp()
    async with app.run_test() as pilot:
        cal = app.query_one(Calendar)
        # Find a day in the current month
        target_day = None
        for day in cal.query(CalendarDay):
            if day.date.month == date.today().month:
                target_day = day
                break
        assert target_day is not None

        await pilot.click(target_day)
        assert app.date_selected == target_day.date
        assert cal.selected == target_day.date


@pytest.mark.asyncio
async def test_selected_has_css_class():
    """Passed-in selected date has 'selected' class."""
    selected = date(2026, 2, 15)
    app = CalendarApp(selected=selected)
    async with app.run_test():
        cal = app.query_one(Calendar)
        for day in cal.query(CalendarDay):
            if day.date == selected:
                assert "selected" in day.classes
                return
        pytest.fail("Selected date not found in calendar")


@pytest.mark.asyncio
async def test_prev_month_navigation(app):
    """<< navigates to previous month."""
    async with app.run_test() as pilot:
        cal = app.query_one(Calendar)
        today = date.today()
        prev_month = today.month - 1 if today.month > 1 else 12
        prev_year = today.year if today.month > 1 else today.year - 1
        expected = date(prev_year, prev_month, 1).strftime("%b %Y")

        prev_btn = cal.query_one("#prev")
        await pilot.click(prev_btn)

        title = cal.query_one("#title")
        assert title.content == expected


@pytest.mark.asyncio
async def test_next_month_navigation(app):
    """>> navigates to next month."""
    async with app.run_test() as pilot:
        cal = app.query_one(Calendar)
        today = date.today()
        next_month = today.month + 1 if today.month < 12 else 1
        next_year = today.year if today.month < 12 else today.year + 1
        expected = date(next_year, next_month, 1).strftime("%b %Y")

        next_btn = cal.query_one("#next")
        await pilot.click(next_btn)

        title = cal.query_one("#title")
        assert title.content == expected


@pytest.mark.asyncio
async def test_other_month_days_dimmed():
    """Days from adjacent months have 'other-month' class."""
    # Use March 2026 which starts on Sunday but has 31 days,
    # so will show April days
    selected = date(2026, 3, 15)
    app = CalendarApp(selected=selected)
    async with app.run_test():
        cal = app.query_one(Calendar)

        # There should be at least some days from other months visible
        other_month_days = [day for day in cal.query(CalendarDay) if day.date.month != 3]
        assert len(other_month_days) > 0

        for day in other_month_days:
            assert "other-month" in day.classes


@pytest.mark.asyncio
async def test_selected_date_shows_its_month():
    """Calendar shows the month of the selected date."""
    selected = date(2025, 6, 15)
    app = CalendarApp(selected=selected)
    async with app.run_test():
        cal = app.query_one(Calendar)
        title = cal.query_one("#title")
        assert title.content == "Jun 2025"


@pytest.mark.asyncio
async def test_clicking_day_updates_selected_class():
    """Clicking a day adds 'selected' class to it."""
    app = CalendarApp()
    async with app.run_test() as pilot:
        cal = app.query_one(Calendar)

        # Find a day in the current month
        target_day = None
        for day in cal.query(CalendarDay):
            if day.date.month == date.today().month and day.date.day == 15:
                target_day = day
                break
        assert target_day is not None

        await pilot.click(target_day)

        # Re-query to get the updated widget
        for day in cal.query(CalendarDay):
            if day.date == target_day.date:
                assert "selected" in day.classes
                return
        pytest.fail("Day not found after clicking")


@pytest.mark.asyncio
async def test_year_wrap_prev():
    """Navigating previous from January goes to December of previous year."""
    selected = date(2026, 1, 15)
    app = CalendarApp(selected=selected)
    async with app.run_test() as pilot:
        cal = app.query_one(Calendar)
        title = cal.query_one("#title")
        assert title.content == "Jan 2026"

        prev_btn = cal.query_one("#prev")
        await pilot.click(prev_btn)

        title = cal.query_one("#title")
        assert title.content == "Dec 2025"


@pytest.mark.asyncio
async def test_year_wrap_next():
    """Navigating next from December goes to January of next year."""
    selected = date(2025, 12, 15)
    app = CalendarApp(selected=selected)
    async with app.run_test() as pilot:
        cal = app.query_one(Calendar)
        title = cal.query_one("#title")
        assert title.content == "Dec 2025"

        next_btn = cal.query_one("#next")
        await pilot.click(next_btn)

        title = cal.query_one("#title")
        assert title.content == "Jan 2026"
