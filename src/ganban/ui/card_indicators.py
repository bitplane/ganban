"""Pure functions for building card indicator text."""

from datetime import date

from rich.text import Text

from ganban.model.node import ListNode, Node
from ganban.parser import first_body
from ganban.ui.cal import date_diff
from ganban.ui.constants import ICON_BLOCKED, ICON_BODY, ICON_CALENDAR, ICON_CHECKED, ICON_COLOR_SWATCH
from ganban.ui.emoji import parse_committer, resolve_email_emoji
from ganban.ui.palette import get_label_color


def build_label_text(meta: Node, board: Node) -> Text:
    """Build colored block characters for a card's labels."""
    card_labels = meta.labels if meta else None
    if not card_labels or not isinstance(card_labels, list):
        return Text()
    result = Text()
    for raw in card_labels:
        color = get_label_color(raw, board)
        result.append(ICON_COLOR_SWATCH, style=color)
    return result


RULE_CHAR = "━"


def build_header_line(meta: Node, board: Node, width: int) -> Text:
    """Build a header line as colored horizontal rules.

    No labels: a single dim rule. With labels: the width is split evenly
    into one colored rule segment per label.
    """
    card_labels = meta.labels if meta else None
    if not card_labels or not isinstance(card_labels, list):
        return Text(RULE_CHAR * width, style="dim")
    n = len(card_labels)
    base, extra = divmod(width, n)
    result = Text()
    for i, raw in enumerate(card_labels):
        seg = base + (1 if i < extra else 0)
        result.append(RULE_CHAR * seg, style=get_label_color(raw, board))
    return result


def build_footer_text(
    sections: ListNode,
    meta: Node,
    board_meta: Node | None = None,
    blocked: bool = False,
) -> Text:
    """Build footer indicators from card sections and meta.

    Shows assignee emoji if meta.assigned is set.
    Shows body icon (dim) if first section has body content.
    Shows calendar icon + Xd if meta.due is set, red if overdue.
    Shows blocked icon if blocked is True.
    """
    parts: list[Text] = []

    # Assignee indicator
    assigned = meta.assigned if meta else None
    if assigned and board_meta:
        _, _, email = parse_committer(assigned)
        parts.append(Text(resolve_email_emoji(email, board_meta)))

    # Body indicator
    body = first_body(sections)
    if body.strip():
        parts.append(Text(ICON_BODY, style="dim"))

    # Due date indicator
    due_str = meta.due if meta else None
    if due_str:
        try:
            due = date.fromisoformat(due_str)
        except (ValueError, TypeError):
            due = None
        if due:
            today = date.today()
            diff = date_diff(due, today)
            style = "red" if due <= today else ""
            parts.append(Text(f"{ICON_CALENDAR}{diff}", style=style))

    # Blocked indicator
    if blocked:
        parts.append(Text(ICON_BLOCKED))

    # Done indicator
    done = meta.done if meta else None
    if done:
        parts.append(Text(ICON_CHECKED, style="dim"))

    if not parts:
        return Text()

    result = parts[0]
    for part in parts[1:]:
        result.append(" ")
        result.append(part)
    return result
