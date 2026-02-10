"""Calendar widget for date selection."""

import calendar
from datetime import date, timedelta

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.message import Message
from textual.widgets import Static

from ganban.ui.constants import ICON_DELETE
from ganban.ui.menu import ContextMenu


def date_diff(target: date, reference: date) -> str:
    """Return compact string showing difference between dates.

    Examples: "1d", "-3d", "2m", "-1m", "5y", "-2y"
    Uses days for <60 days, months for <24 months, years otherwise.
    """
    days = (target - reference).days
    if days == 0:
        return "0d"

    sign = "" if days > 0 else "-"
    abs_days = abs(days)

    if abs_days < 60:
        return f"{sign}{abs_days}d"

    # Calculate month difference
    months = (target.year - reference.year) * 12 + (target.month - reference.month)
    abs_months = abs(months)

    if abs_months < 24:
        return f"{sign}{abs_months}m"

    # Years
    years = abs(target.year - reference.year)
    return f"{sign}{years}y"


class NavButton(Static):
    """Navigation button for calendar."""

    class Clicked(Message):
        def __init__(self, button: "NavButton") -> None:
            super().__init__()
            self.button = button

    def on_click(self, event) -> None:
        event.stop()
        self.post_message(self.Clicked(self))


class CalendarDay(Static, can_focus=True):
    """A single day cell."""

    class Clicked(Message):
        """Posted when this day is clicked."""

        def __init__(self, day: "CalendarDay") -> None:
            super().__init__()
            self.day = day

    def __init__(self, d: date, **kwargs) -> None:
        super().__init__(str(d.day).rjust(2), **kwargs)
        self.date = d

    def on_click(self, event) -> None:
        event.stop()
        self.post_message(self.Clicked(self))


class Calendar(Container):
    """Date picker widget."""

    class DateSelected(Message):
        """Emitted when a date is selected (None to clear)."""

        def __init__(self, selected: date | None) -> None:
            super().__init__()
            self.date = selected

        @property
        def control(self) -> "Calendar":
            return self._sender

    DEFAULT_CSS = """
    Calendar { width: auto; height: auto; background: $background; }
    .cal-header { width: 100%; height: 1; }
    .cal-nav { width: 2; }
    .cal-clear { width: auto; padding: 0 1; }
    .cal-title { width: 1fr; text-align: center; }
    .cal-grid { width: auto; height: auto; }
    .cal-row { width: auto; height: 1; }
    .cal-label { width: 3; color: $text-muted; }
    CalendarDay { width: 3; text-align: center; }
    CalendarDay:hover { background: $primary-darken-2; }
    CalendarDay:focus { background: $primary-darken-2; }
    CalendarDay.today { text-style: bold; color: $primary; }
    CalendarDay.selected { background: $primary; color: $text; }
    CalendarDay.other-month { color: $text-disabled; }
    """

    BINDINGS = [
        ("up", "cursor_up", "Previous day"),
        ("down", "cursor_down", "Next day"),
        ("left", "cursor_left", "Previous week"),
        ("right", "cursor_right", "Next week"),
        ("enter", "select", "Select date"),
        ("pageup", "prev_month", "Previous month"),
        ("pagedown", "next_month", "Next month"),
    ]

    def __init__(self, selected: date | None = None) -> None:
        super().__init__()
        self._selected = selected
        self._viewing = date.today().replace(day=1)
        self._cursor_date: date | None = None
        if selected:
            self._viewing = selected.replace(day=1)

    @property
    def selected(self) -> date | None:
        return self._selected

    def compose(self) -> ComposeResult:
        with Horizontal(classes="cal-header"):
            yield NavButton("<<", classes="cal-nav", id="prev")
            yield NavButton(ICON_DELETE, classes="cal-nav cal-clear", id="clear")
            yield Static(self._viewing.strftime("%b %Y"), classes="cal-title", id="title")
            yield NavButton(">>", classes="cal-nav", id="next")

        yield self._build_grid()

    def _build_grid(self) -> Vertical:
        """Build the calendar grid."""
        grid = Vertical(classes="cal-grid")
        for dow in range(7):  # Sun=0 through Sat=6
            row = Horizontal(classes="cal-row")
            row.compose_add_child(Static(["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"][dow], classes="cal-label"))
            for d in self._days_for_row(dow):
                row.compose_add_child(self._make_day(d))
            grid.compose_add_child(row)
        return grid

    def _days_for_row(self, day_of_week: int) -> list[date]:
        """Get 6 dates for a given day-of-week in current month view."""
        cal = calendar.Calendar(firstweekday=6)  # Sunday first
        weeks = cal.monthdatescalendar(self._viewing.year, self._viewing.month)
        days = [week[day_of_week] for week in weeks]
        # Pad to 6 columns if needed
        while len(days) < 6:
            last = days[-1]
            days.append(last + timedelta(days=7))
        return days[:6]

    def _make_day(self, d: date) -> CalendarDay:
        """Create a day cell with appropriate CSS classes."""
        classes = []
        if d == date.today():
            classes.append("today")
        if d == self._selected:
            classes.append("selected")
        if d.month != self._viewing.month:
            classes.append("other-month")
        return CalendarDay(d, classes=" ".join(classes))

    def on_mount(self) -> None:
        self.call_after_refresh(self._focus_initial)

    @property
    def _focused_day(self) -> CalendarDay | None:
        focused = self.app.focused
        return focused if isinstance(focused, CalendarDay) else None

    def _focus_date(self, target: date) -> None:
        """Focus the CalendarDay matching target date."""
        for day in self.query(CalendarDay):
            if day.date == target:
                day.focus()
                return

    def _focus_initial(self) -> None:
        """Focus selected date if set, else today if visible, else 1st of month."""
        if self._selected:
            self._focus_date(self._selected)
            return
        today = date.today()
        if today.month == self._viewing.month and today.year == self._viewing.year:
            self._focus_date(today)
            return
        self._focus_date(self._viewing.replace(day=1))

    def _navigate(self, delta_days: int) -> None:
        """Move cursor by delta_days from focused day."""
        focused = self._focused_day
        if not focused:
            return
        target = focused.date + timedelta(days=delta_days)
        self._cursor_date = target
        # Check if target is in current grid
        for day in self.query(CalendarDay):
            if day.date == target:
                day.focus()
                return
        # Target not visible — change month and focus after refresh
        self._viewing = target.replace(day=1)
        self._refresh()
        self.call_after_refresh(self._focus_date, target)

    def action_cursor_up(self) -> None:
        self._navigate(-1)

    def action_cursor_down(self) -> None:
        self._navigate(1)

    def action_cursor_left(self) -> None:
        self._navigate(-7)

    def action_cursor_right(self) -> None:
        self._navigate(7)

    def action_select(self) -> None:
        focused = self._focused_day
        if not focused:
            return
        self._selected = focused.date
        self.post_message(self.DateSelected(focused.date))
        self._refresh()
        self.call_after_refresh(self._focus_date, focused.date)

    def action_prev_month(self) -> None:
        focused = self._focused_day
        self._go_prev_month()
        if focused:
            # Try same day-of-month in new month, clamped
            max_day = calendar.monthrange(self._viewing.year, self._viewing.month)[1]
            target = self._viewing.replace(day=min(focused.date.day, max_day))
            self._cursor_date = target
            self.call_after_refresh(self._focus_date, target)

    def action_next_month(self) -> None:
        focused = self._focused_day
        self._go_next_month()
        if focused:
            max_day = calendar.monthrange(self._viewing.year, self._viewing.month)[1]
            target = self._viewing.replace(day=min(focused.date.day, max_day))
            self._cursor_date = target
            self.call_after_refresh(self._focus_date, target)

    def on_nav_button_clicked(self, event: NavButton.Clicked) -> None:
        event.stop()
        if event.button.id == "clear":
            self._selected = None
            self.post_message(self.DateSelected(None))
        elif event.button.id == "prev":
            self._go_prev_month()
        elif event.button.id == "next":
            self._go_next_month()

    def on_calendar_day_clicked(self, event: CalendarDay.Clicked) -> None:
        event.stop()
        self._selected = event.day.date
        self.post_message(self.DateSelected(event.day.date))
        self._refresh()

    def _go_prev_month(self) -> None:
        if self._viewing.month == 1:
            self._viewing = self._viewing.replace(year=self._viewing.year - 1, month=12)
        else:
            self._viewing = self._viewing.replace(month=self._viewing.month - 1)
        self._refresh()

    def _go_next_month(self) -> None:
        if self._viewing.month == 12:
            self._viewing = self._viewing.replace(year=self._viewing.year + 1, month=1)
        else:
            self._viewing = self._viewing.replace(month=self._viewing.month + 1)
        self._refresh()

    def _refresh(self) -> None:
        """Rebuild the calendar grid."""
        focused = self._focused_day
        cursor = focused.date if focused else self._cursor_date
        self.query_one("#title", Static).update(self._viewing.strftime("%b %Y"))
        old_grid = self.query_one(".cal-grid")
        new_grid = self._build_grid()
        old_grid.remove()
        self.mount(new_grid)
        if cursor:
            self.call_after_refresh(self._focus_date, cursor)


class CalendarMenuItem(Container):
    """Menu item containing a calendar picker."""

    class Selected(Message):
        """Posted when a date is selected, signals menu to close."""

        def __init__(self, item: "CalendarMenuItem") -> None:
            super().__init__()
            self.item = item

    DEFAULT_CSS = """
    CalendarMenuItem {
        width: auto;
        height: auto;
    }
    """

    def __init__(self, selected: date | None = None) -> None:
        super().__init__()
        self._initial = selected
        self.selected_date: date | None = selected

    def compose(self) -> ComposeResult:
        yield Calendar(selected=self._initial)

    def on_calendar_date_selected(self, event: Calendar.DateSelected) -> None:
        event.stop()
        self.selected_date = event.date
        self.post_message(self.Selected(self))


class DateButton(Static):
    """A button that opens a calendar menu for date selection."""

    class DateSelected(Message):
        """Emitted when a date is selected (None to clear)."""

        def __init__(self, selected: date | None) -> None:
            super().__init__()
            self.date = selected

        @property
        def control(self) -> "DateButton":
            return self._sender

    DEFAULT_CSS = """
    DateButton {
        width: 2;
        height: 1;
    }
    DateButton:hover {
        background: $primary-darken-2;
    }
    """

    def __init__(self, selected: date | None = None, icon: str = "🗓️", **kwargs) -> None:
        super().__init__(icon, **kwargs)
        self._selected = selected

    @property
    def selected(self) -> date | None:
        return self._selected

    def on_click(self, event) -> None:
        event.stop()
        # Position at button, not mouse (for keyboard accessibility)
        x = self.region.x
        y = self.region.y + 1  # Below the button
        menu = ContextMenu([CalendarMenuItem(self._selected)], x, y)
        self.app.push_screen(menu, self._on_menu_closed)

    def _on_menu_closed(self, result) -> None:
        if isinstance(result, CalendarMenuItem):
            self._selected = result.selected_date
            self.post_message(self.DateSelected(result.selected_date))
