"""Dependency editor widget for card detail bar."""

from __future__ import annotations

from ganban.model.node import Node
from ganban.parser import first_title
from ganban.ui.tag import TagListWidget

ICON_DEPS = "\U0001f517"  # 🔗


def build_card_options(board: Node, exclude: str | set[str] = "") -> list[tuple[str, str]]:
    """Build (label, value) options for card references.

    Returns all non-archived cards, excluding the given id(s).
    The label is ``"ID Title"`` and the value is the card ID.
    """
    excluded = {exclude} if isinstance(exclude, str) else set(exclude)
    options: list[tuple[str, str]] = []
    for cid, card in board.cards.items():
        if cid in excluded or card.archived:
            continue
        title = first_title(card.sections) if card.sections else cid
        options.append((f"{cid} {title}", cid))
    return options


def build_dep_options(board: Node, card_id: str, current_deps: list[str]) -> list[tuple[str, str]]:
    """Build options for the dep search dropdown: non-archived cards minus
    the current card and existing deps."""
    return build_card_options(board, {card_id, *current_deps})


class DepsWidget(TagListWidget):
    """Inline deps editor for card detail bar.

    Displays dep IDs next to a link icon. Click the icon to add a dep,
    click a tag to edit it, click × to delete. Uses Tag widgets with
    SearchInput for card selection.
    """

    meta_key = "deps"
    icon = ICON_DEPS
    bar_id = "deps-bar"
    add_id = "deps-add"
    tags_id = "deps-tags"

    def __init__(self, meta: Node, board: Node, card_id: str, **kwargs) -> None:
        super().__init__(meta, board, **kwargs)
        self.card_id = card_id

    def options_for(self, current: list[str]) -> list[tuple[str, str]]:
        return build_dep_options(self.board, self.card_id, current)

    def validate(self, value: str) -> bool:
        return value in self.board.cards
