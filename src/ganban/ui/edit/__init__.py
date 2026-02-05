"""Editable widget components."""

from ganban.ui.edit.document import MarkdownDocEditor
from ganban.ui.edit.label import EditableLabel, PlainStatic
from ganban.ui.edit.markdown import EditableMarkdown
from ganban.ui.edit.section import SectionEditor

__all__ = [
    "EditableLabel",
    "EditableMarkdown",
    "MarkdownDocEditor",
    "PlainStatic",
    "SectionEditor",
]
