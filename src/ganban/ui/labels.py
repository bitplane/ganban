"""Label editor widget for card detail bar."""

from __future__ import annotations

from rich.text import Text
from textual.widgets import Input, OptionList, Static

from ganban.model.loader import normalise_label
from ganban.model.node import Node
from ganban.ui.constants import ICON_COLOR_SWATCH
from ganban.ui.palette import get_label_color
from ganban.ui.tag import TagListWidget

ICON_LABEL = "\U0001f516"  # 🔖


def _label_display(name: str, board: Node) -> Text:
    """Build a colored block + name Text for a label."""
    color = get_label_color(name, board)
    result = Text()
    result.append(ICON_COLOR_SWATCH, style=color)
    result.append_text(Text(name))
    return result


def build_label_options(board: Node, current_labels: list[str]) -> list[tuple[str, str]]:
    """Build (label, value) options for the label search dropdown.

    Shows all known labels from board.labels, excluding those already on the card.
    """
    exclude = {normalise_label(raw) for raw in current_labels}
    options: list[tuple[str, str]] = []
    if board.labels:
        for name in board.labels.keys():
            if name not in exclude:
                options.append((name, name))
    return options


class LabelsWidget(TagListWidget):
    """Inline label editor for card detail bar.

    Displays label tags next to a bookmark icon. Click the icon to add a label,
    click a tag to edit it, click × to delete. Uses Tag widgets with SearchInput
    for label selection with free-text fallback for new labels.
    """

    meta_key = "labels"
    icon = ICON_LABEL
    bar_id = "labels-bar"
    add_id = "labels-add"
    tags_id = "labels-tags"

    def display_for(self, value: str) -> Text:
        return _label_display(value, self.board)

    def options_for(self, current: list[str]) -> list[tuple[str, str]]:
        return build_label_options(self.board, current)

    def _swatch_for(self, text: str) -> Text:
        """Build a swatch-only Text for the given label name."""
        name = normalise_label(text)
        if name:
            color = get_label_color(name, self.board)
            result = Text()
            result.append(ICON_COLOR_SWATCH, style=color)
            return result
        return Text()

    def _update_editing_swatch(self, text: str) -> None:
        """Update the tag-label on whichever tag is currently editing."""
        for tag in self._tags():
            if tag.has_class("-editing"):
                tag.query_one(".tag-label", Static).update(self._swatch_for(text))
                return

    def on_input_changed(self, event: Input.Changed) -> None:
        event.stop()
        self._update_editing_swatch(event.value)

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        event.stop()
        if event.option and event.option.id:
            self._update_editing_swatch(event.option.id)
