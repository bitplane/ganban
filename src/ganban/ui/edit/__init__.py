"""Editable widget components."""

from ganban.ui.edit.document import MarkdownDocEditor
from ganban.ui.edit.label import EditableLabel
from ganban.ui.edit.markdown import EditableMarkdown
from ganban.ui.edit.section import SectionEditor
from ganban.ui.static import PlainStatic

__all__ = [
    "EditableLabel",
    "EditableMarkdown",
    "MarkdownDocEditor",
    "PlainStatic",
    "SectionEditor",
]
