"""Tests for the calendar widget."""

from datetime import date

import pytest
from textual.app import App, ComposeResult

from ganban.ui.cal import Calendar, CalendarDay, CalendarMenuItem, DateButton, date_diff
from ganban.ui.menu import ContextMenu


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


# date_diff tests


def test_date_diff_same_day():
    """Same date returns 0d."""
    ref = date(2026, 2, 15)
    assert date_diff(ref, ref) == "0d"


def test_date_diff_days_future():
    """Days in the future."""
    ref = date(2026, 2, 15)
    assert date_diff(date(2026, 2, 16), ref) == "1d"
    assert date_diff(date(2026, 2, 20), ref) == "5d"
    assert date_diff(date(2026, 3, 15), ref) == "28d"


def test_date_diff_days_past():
    """Days in the past have minus sign."""
    ref = date(2026, 2, 15)
    assert date_diff(date(2026, 2, 14), ref) == "-1d"
    assert date_diff(date(2026, 2, 10), ref) == "-5d"
    assert date_diff(date(2026, 1, 20), ref) == "-26d"


def test_date_diff_months_future():
    """Months for 60+ days in future."""
    ref = date(2026, 2, 15)
    assert date_diff(date(2026, 5, 15), ref) == "3m"
    assert date_diff(date(2027, 1, 15), ref) == "11m"


def test_date_diff_months_past():
    """Months for 60+ days in past."""
    ref = date(2026, 6, 15)
    assert date_diff(date(2026, 3, 15), ref) == "-3m"
    assert date_diff(date(2025, 8, 15), ref) == "-10m"


def test_date_diff_years_future():
    """Years for 24+ months in future."""
    ref = date(2026, 2, 15)
    assert date_diff(date(2028, 3, 15), ref) == "2y"
    assert date_diff(date(2031, 2, 15), ref) == "5y"


def test_date_diff_years_past():
    """Years for 24+ months in past."""
    ref = date(2026, 6, 15)
    assert date_diff(date(2024, 5, 15), ref) == "-2y"
    assert date_diff(date(2021, 6, 15), ref) == "-5y"


def test_date_diff_boundary_59_days():
    """59 days still shows days."""
    ref = date(2026, 1, 1)
    assert date_diff(date(2026, 3, 1), ref) == "59d"


def test_date_diff_boundary_60_days():
    """60 days switches to months."""
    ref = date(2026, 1, 1)
    assert date_diff(date(2026, 3, 2), ref) == "2m"


def test_date_diff_boundary_23_months():
    """23 months still shows months."""
    ref = date(2026, 1, 15)
    assert date_diff(date(2027, 12, 15), ref) == "23m"


def test_date_diff_boundary_24_months():
    """24 months switches to years."""
    ref = date(2026, 1, 15)
    assert date_diff(date(2028, 1, 15), ref) == "2y"


# DateButton tests


class DateButtonApp(App):
    """Minimal app for testing date button."""

    def __init__(self, selected: date | None = None):
        super().__init__()
        self._selected = selected
        self.date_selected: date | None = None

    def compose(self) -> ComposeResult:
        yield DateButton(selected=self._selected)

    def on_date_button_date_selected(self, event: DateButton.DateSelected) -> None:
        self.date_selected = event.date


@pytest.mark.asyncio
async def test_date_button_displays_icon():
    """DateButton displays calendar icon."""
    app = DateButtonApp()
    async with app.run_test():
        btn = app.query_one(DateButton)
        assert btn.content == "🗓️"


@pytest.mark.asyncio
async def test_date_button_click_opens_menu():
    """Clicking DateButton opens ContextMenu with calendar."""
    app = DateButtonApp()
    async with app.run_test() as pilot:
        btn = app.query_one(DateButton)
        await pilot.click(btn)
        assert isinstance(app.screen, ContextMenu)
        assert app.screen.query_one(CalendarMenuItem)


@pytest.mark.asyncio
async def test_date_button_selecting_date_emits_message():
    """Selecting a date emits DateSelected message."""
    app = DateButtonApp()
    async with app.run_test() as pilot:
        btn = app.query_one(DateButton)
        await pilot.click(btn)

        # Click a day in the calendar
        cal = app.screen.query_one(Calendar)
        target_day = None
        for day in cal.query(CalendarDay):
            if day.date.month == date.today().month:
                target_day = day
                break

        await pilot.click(target_day)

        # Menu should close and message should be emitted
        assert not isinstance(app.screen, ContextMenu)
        assert app.date_selected == target_day.date
        assert btn.selected == target_day.date


@pytest.mark.asyncio
async def test_date_button_escape_cancels():
    """Pressing escape closes menu without selecting."""
    app = DateButtonApp()
    async with app.run_test() as pilot:
        btn = app.query_one(DateButton)
        await pilot.click(btn)
        assert isinstance(app.screen, ContextMenu)

        await pilot.press("escape")

        assert not isinstance(app.screen, ContextMenu)
        assert app.date_selected is None


@pytest.mark.asyncio
async def test_date_button_with_initial_selection():
    """DateButton with initial selection shows that date in calendar."""
    selected = date(2026, 3, 20)
    app = DateButtonApp(selected=selected)
    async with app.run_test() as pilot:
        btn = app.query_one(DateButton)
        assert btn.selected == selected

        await pilot.click(btn)
        cal = app.screen.query_one(Calendar)

        # Check calendar shows March 2026
        title = cal.query_one("#title")
        assert title.content == "Mar 2026"

        # Check selected date has class
        for day in cal.query(CalendarDay):
            if day.date == selected:
                assert "selected" in day.classes
                return
        pytest.fail("Selected date not found")
