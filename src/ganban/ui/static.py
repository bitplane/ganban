"""Static widget variants."""

from textual.widgets import Static


class PlainStatic(Static):
    """Static that doesn't allow text selection."""

    ALLOW_SELECT = False
