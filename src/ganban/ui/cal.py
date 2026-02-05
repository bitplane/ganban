"""Calendar widget for date selection."""

import calendar
from datetime import date

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.message import Message
from textual.widgets import Static


class CalendarDay(Static):
    """A single day cell."""

    def __init__(self, d: date, **kwargs) -> None:
        super().__init__(str(d.day).rjust(2), **kwargs)
        self.date = d


class Calendar(Container):
    """Date picker widget."""

    class DateSelected(Message):
        """Emitted when a date is selected."""

        def __init__(self, selected: date) -> None:
            super().__init__()
            self.date = selected

        @property
        def control(self) -> "Calendar":
            return self._sender

    DEFAULT_CSS = """
    Calendar { width: auto; height: auto; }
    .cal-header { width: 100%; height: 1; }
    .cal-nav { width: 2; }
    .cal-title { width: 1fr; text-align: center; }
    .cal-grid { width: auto; height: auto; }
    .cal-row { width: auto; height: 1; }
    .cal-label { width: 3; color: $text-muted; }
    CalendarDay { width: 3; text-align: right; }
    CalendarDay:hover { background: $primary-darken-2; }
    CalendarDay.today { text-style: bold; color: $primary; }
    CalendarDay.selected { background: $primary; color: $text; }
    CalendarDay.other-month { color: $text-disabled; }
    """

    def __init__(self, selected: date | None = None) -> None:
        super().__init__()
        self._selected = selected
        self._viewing = date.today().replace(day=1)
        if selected:
            self._viewing = selected.replace(day=1)

    @property
    def selected(self) -> date | None:
        return self._selected

    def compose(self) -> ComposeResult:
        with Horizontal(classes="cal-header"):
            yield Static("<<", classes="cal-nav", id="prev")
            yield Static(self._viewing.strftime("%b %Y"), classes="cal-title", id="title")
            yield Static(">>", classes="cal-nav", id="next")

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
        """Get all dates for a given day-of-week in current month view."""
        cal = calendar.Calendar(firstweekday=6)  # Sunday first
        weeks = cal.monthdatescalendar(self._viewing.year, self._viewing.month)
        return [week[day_of_week] for week in weeks]

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

    def on_click(self, event) -> None:
        widget, _ = self.app.get_widget_at(event.screen_x, event.screen_y)

        if widget.id == "prev":
            self._go_prev_month()
        elif widget.id == "next":
            self._go_next_month()
        elif isinstance(widget, CalendarDay):
            self._selected = widget.date
            self.post_message(self.DateSelected(widget.date))
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
        self.query_one("#title", Static).update(self._viewing.strftime("%b %Y"))
        old_grid = self.query_one(".cal-grid")
        new_grid = self._build_grid()
        old_grid.remove()
        self.mount(new_grid)
