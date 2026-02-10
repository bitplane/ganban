"""Users editor for board meta."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.message import Message
from textual.widgets import Static

from ganban.model.node import Node
from ganban.ui.confirm import ConfirmButton
from ganban.ui.edit.editable import EditableText
from ganban.ui.edit.editors import TextEditor
from ganban.ui.edit.viewers import TextViewer
from ganban.ui.emoji import EmojiButton, parse_committer
from ganban.ui.search import SearchInput
from ganban.ui.watcher import NodeWatcherMixin


def _build_email_options(committers: list[str] | None, exclude: set[str] | None = None) -> list[tuple[str, str]]:
    """Build (label, value) options for the email search from git committers.

    Labels show "Name <email>", values are the bare email address.
    """
    if not committers:
        return []
    exclude = exclude or set()
    options: list[tuple[str, str]] = []
    seen: set[str] = set()
    for committer_str in committers:
        _, name, email = parse_committer(committer_str)
        if email not in seen and email not in exclude:
            options.append((f"{name} <{email}>", email))
            seen.add(email)
    return options


class EmailTag(Container, can_focus=True):
    """A single email address tag — click to edit with committer search."""

    BINDINGS = [
        ("space", "start_editing"),
        ("enter", "start_editing"),
    ]

    class ValueChanged(Message):
        def __init__(self, index: int, value: str) -> None:
            super().__init__()
            self.index = index
            self.value = value

    def __init__(self, index: int, email: str, committers: list[str] | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.index = index
        self.email = email
        self._committers = committers

    def compose(self) -> ComposeResult:
        yield Static(self.email or '""', classes="email-label")
        yield SearchInput([], placeholder="email@address", value=self.email, classes="email-search")

    def action_start_editing(self) -> None:
        self.add_class("-editing")
        search = self.query_one(SearchInput)
        search.set_options(_build_email_options(self._committers, self._sibling_emails()))
        inp = search.query_one("Input")
        inp.value = self.email
        inp.focus()

    def _sibling_emails(self) -> set[str]:
        result: set[str] = set()
        if self.parent:
            for tag in self.parent.query(EmailTag):
                if tag is not self and tag.email:
                    result.add(tag.email)
        return result

    def on_click(self, event) -> None:
        event.stop()
        if not self.has_class("-editing"):
            self.action_start_editing()

    def on_search_input_submitted(self, event: SearchInput.Submitted) -> None:
        event.stop()
        new_email = (event.value or event.text).strip()
        self.remove_class("-editing")
        self.email = new_email
        self.query_one(".email-label", Static).update(new_email or '""')
        self.post_message(self.ValueChanged(self.index, new_email))
        self.focus()

    def on_search_input_cancelled(self, event: SearchInput.Cancelled) -> None:
        event.stop()
        self.remove_class("-editing")
        self.focus()


class AddEmailButton(Container, can_focus=True):
    """Searchable input to add a new email address from git committers."""

    BINDINGS = [
        ("space", "start_editing"),
        ("enter", "start_editing"),
    ]

    class EmailAdded(Message):
        def __init__(self, email: str) -> None:
            super().__init__()
            self.email = email

    def __init__(self, committers: list[str] | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._committers = committers

    def action_start_editing(self) -> None:
        self.add_class("-editing")
        search = self.query_one(SearchInput)
        search.set_options(self._get_options())
        inp = search.query_one("Input")
        inp.value = ""
        inp.focus()

    def _get_options(self) -> list[tuple[str, str]]:
        exclude = self._get_sibling_emails()
        return _build_email_options(self._committers, exclude)

    def _get_sibling_emails(self) -> set[str]:
        result: set[str] = set()
        if self.parent:
            for tag in self.parent.query(EmailTag):
                if tag.email:
                    result.add(tag.email)
        return result

    def compose(self) -> ComposeResult:
        yield Static("+", classes="add-email-label")
        yield SearchInput([], placeholder="email@address", classes="add-email-search")

    def on_click(self, event) -> None:
        event.stop()
        if not self.has_class("-editing"):
            self.action_start_editing()

    def on_search_input_submitted(self, event: SearchInput.Submitted) -> None:
        event.stop()
        email = (event.value or event.text).strip()
        if email:
            self.post_message(self.EmailAdded(email))
        self.remove_class("-editing")
        self.focus()

    def on_search_input_cancelled(self, event: SearchInput.Cancelled) -> None:
        event.stop()
        self.remove_class("-editing")
        self.focus()


class UserRow(Vertical):
    """A single user card with title bar and email list."""

    class NameRenamed(Message):
        def __init__(self, old: str, new: str) -> None:
            super().__init__()
            self.old = old
            self.new = new

    class EmojiChanged(Message):
        def __init__(self, name: str, emoji: str | None) -> None:
            super().__init__()
            self.name = name
            self.emoji = emoji

    class EmailsChanged(Message):
        def __init__(self, name: str, emails: list[str]) -> None:
            super().__init__()
            self.name = name
            self.emails = emails

    class DeleteRequested(Message):
        def __init__(self, name: str) -> None:
            super().__init__()
            self.name = name

    def __init__(self, user_name: str, user_node: Node, committers: list[str] | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.user_name = user_name
        self.user_node = user_node
        self._committers = committers
        self._emails: list[str] = list(user_node.emails) if isinstance(user_node.emails, list) else []

    @property
    def _first_email(self) -> str | None:
        return self._emails[0] if self._emails else None

    def compose(self) -> ComposeResult:
        with Horizontal(classes="user-title-bar"):
            yield EmojiButton(self.user_node.emoji, email=self._first_email, classes="user-emoji")
            yield EditableText(
                self.user_name,
                TextViewer(self.user_name),
                TextEditor(),
                classes="user-name",
            )
            yield ConfirmButton(classes="user-delete")
        with Vertical(classes="user-emails"):
            for i, email in enumerate(self._emails):
                yield EmailTag(i, email, committers=self._committers)
            yield AddEmailButton(committers=self._committers)

    def _reindex_emails(self) -> None:
        for i, tag in enumerate(self.query(EmailTag)):
            tag.index = i

    def _update_emoji_default(self) -> None:
        self.query_one(EmojiButton).email = self._first_email

    def on_editable_text_changed(self, event: EditableText.Changed) -> None:
        event.stop()
        sender = event.control
        if "user-name" in sender.classes:
            old = self.user_name
            self.user_name = event.new_value
            self.post_message(self.NameRenamed(old, event.new_value))

    def on_emoji_button_emoji_selected(self, event: EmojiButton.EmojiSelected) -> None:
        event.stop()
        self.post_message(self.EmojiChanged(self.user_name, event.emoji))

    def on_confirm_button_confirmed(self, event: ConfirmButton.Confirmed) -> None:
        event.stop()
        self.post_message(self.DeleteRequested(self.user_name))

    def on_email_tag_value_changed(self, event: EmailTag.ValueChanged) -> None:
        event.stop()
        if event.value:
            self._emails[event.index] = event.value
        else:
            del self._emails[event.index]
            tags = list(self.query(EmailTag))
            tags[event.index].remove()
            self._reindex_emails()
        self._update_emoji_default()
        self.post_message(self.EmailsChanged(self.user_name, list(self._emails)))

    def on_add_email_button_email_added(self, event: AddEmailButton.EmailAdded) -> None:
        event.stop()
        self._emails.append(event.email)
        tag = EmailTag(len(self._emails) - 1, event.email, committers=self._committers)
        emails_container = self.query_one(".user-emails")
        self.app.call_later(emails_container.mount, tag, before=emails_container.query_one(AddEmailButton))
        self.post_message(self.EmailsChanged(self.user_name, list(self._emails)))


class AddUserRow(Static, can_focus=True):
    """EditableText with '+' to add a new user."""

    BINDINGS = [
        ("space", "start_editing"),
        ("enter", "start_editing"),
    ]

    class UserCreated(Message):
        def __init__(self, name: str) -> None:
            super().__init__()
            self.name = name

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    def action_start_editing(self) -> None:
        self.query_one(EditableText)._start_edit()

    def compose(self) -> ComposeResult:
        yield EditableText("", Static("+"), TextEditor(), placeholder="+")

    def on_editable_text_changed(self, event: EditableText.Changed) -> None:
        event.stop()
        if event.new_value:
            self.post_message(self.UserCreated(event.new_value))
        self.query_one(EditableText).value = ""
        self.focus()


class UsersEditor(NodeWatcherMixin, Container):
    """Editor for board.meta.users -- a dict of display name -> user info."""

    def __init__(self, board: Node, **kwargs) -> None:
        self._init_watcher()
        super().__init__(**kwargs)
        self.board = board
        self.meta = board.meta

    @property
    def _committers(self) -> list[str] | None:
        committers = self.board.git.committers if self.board.git else None
        return committers if isinstance(committers, list) else None

    def _ensure_users(self) -> Node:
        """Create meta.users = {} if missing, return the users node."""
        if self.meta.users is None:
            self.meta.users = {}
        return self.meta.users

    def compose(self) -> ComposeResult:
        users = self.meta.users
        if users is not None:
            for name, user_node in users.items():
                yield UserRow(name, user_node, committers=self._committers)
        yield AddUserRow()

    def on_mount(self) -> None:
        self.node_watch(self.meta, "users", self._on_users_changed)

    def _on_users_changed(self, source_node: Any, key: str, old: Any, new: Any) -> None:
        self.call_later(self.recompose)

    def on_user_row_name_renamed(self, event: UserRow.NameRenamed) -> None:
        event.stop()
        users = self._ensure_users()
        with self.suppressing():
            users.rename_key(event.old, event.new)

    def on_user_row_emoji_changed(self, event: UserRow.EmojiChanged) -> None:
        event.stop()
        users = self._ensure_users()
        user = getattr(users, event.name)
        with self.suppressing():
            user.emoji = event.emoji

    def on_user_row_emails_changed(self, event: UserRow.EmailsChanged) -> None:
        event.stop()
        users = self._ensure_users()
        user = getattr(users, event.name)
        with self.suppressing():
            user.emails = event.emails

    def on_user_row_delete_requested(self, event: UserRow.DeleteRequested) -> None:
        event.stop()
        users = self._ensure_users()
        with self.suppressing():
            setattr(users, event.name, None)
        for row in self.query(UserRow):
            if row.user_name == event.name:
                row.remove()
                break

    def on_add_user_row_user_created(self, event: AddUserRow.UserCreated) -> None:
        event.stop()
        users = self._ensure_users()
        name = event.name
        with self.suppressing():
            setattr(users, name, {"emails": []})
        user_node = getattr(users, name)
        row = UserRow(name, user_node, committers=self._committers)
        self.mount(row, before=self.query_one(AddUserRow))
