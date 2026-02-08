"""Pure functions for building card indicator text."""

from datetime import date

from rich.text import Text

from ganban.model.node import ListNode, Node
from ganban.parser import first_body
from ganban.ui.cal import date_diff
from ganban.ui.constants import ICON_BODY, ICON_CALENDAR, ICON_CHECKED
from ganban.ui.emoji import parse_committer, resolve_email_emoji


def build_footer_text(sections: ListNode, meta: Node, board_meta: Node | None = None) -> Text:
    """Build footer indicators from card sections and meta.

    Shows assignee emoji if meta.assigned is set.
    Shows body icon (dim) if first section has body content.
    Shows calendar icon + Xd if meta.due is set, red if overdue.
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
