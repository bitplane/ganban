"""Pure functions for building card indicator text."""

from datetime import date

from rich.text import Text

from ganban.model.node import ListNode, Node
from ganban.parser import first_body
from ganban.ui.cal import date_diff


def build_footer_text(sections: ListNode, meta: Node) -> Text:
    """Build footer indicators from card sections and meta.

    Shows 📝 (dim) if first section has body content.
    Shows 📅Xd if meta.due is set, red if overdue.
    """
    parts: list[Text] = []

    # Body indicator
    body = first_body(sections)
    if body.strip():
        parts.append(Text("📝", style="dim"))

    # Due date indicator
    due_str = meta.due if meta else None
    if due_str:
        due = date.fromisoformat(due_str)
        today = date.today()
        diff = date_diff(due, today)
        style = "red" if due <= today else ""
        parts.append(Text(f"📅{diff}", style=style))

    if not parts:
        return Text()

    result = parts[0]
    for part in parts[1:]:
        result.append(" ")
        result.append(part)
    return result
