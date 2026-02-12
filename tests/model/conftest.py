"""Shared test helpers for model tests."""

import pytest
from git import Repo

from ganban.model.column import build_column_path
from ganban.model.node import ListNode, Node


def _make_card(title, body="", meta=None):
    """Helper to build a card Node with sections."""
    sections = ListNode()
    sections[title] = body
    return Node(sections=sections, meta=meta or {})


def _make_board(repo_path, columns=None, cards=None, sections=None, meta=None):
    """Helper to build a board Node."""
    board = Node(repo_path=str(repo_path))

    cards_ln = ListNode()
    for card_id, card in (cards or {}).items():
        cards_ln[card_id] = card
    board.cards = cards_ln

    columns_ln = ListNode()
    for col in columns or []:
        columns_ln[col.order] = col
    board.columns = columns_ln

    board.sections = sections or ListNode()
    board.meta = meta or {}

    return board


def _make_column(order, name, links=None, hidden=False, sections=None, meta=None):
    """Helper to build a column Node."""
    if sections is None:
        sections = ListNode()
        sections[name] = ""
    return Node(
        order=order,
        dir_path=build_column_path(order, name, hidden),
        hidden=hidden,
        links=links or [],
        sections=sections,
        meta=meta or {},
    )


@pytest.fixture
def empty_repo(tmp_path):
    """Create an empty git repo."""
    repo = Repo.init(tmp_path)
    (tmp_path / ".gitkeep").write_text("")
    repo.index.add([".gitkeep"])
    repo.index.commit("Initial commit")
    return tmp_path


@pytest.fixture
def repo_with_ganban(empty_repo):
    """Create a repo with an existing ganban branch."""
    repo = Repo(empty_repo)

    repo.git.checkout("--orphan", "ganban")
    repo.git.rm("-rf", ".", "--cached")
    repo.git.clean("-fd")

    all_dir = empty_repo / ".all"
    all_dir.mkdir()
    (all_dir / "001.md").write_text("# First card\n\nDescription.\n")

    backlog = empty_repo / "1.backlog"
    backlog.mkdir()
    (backlog / "01.first-card.md").symlink_to("../.all/001.md")

    repo.git.add("-A")
    repo.index.commit("Initial board")

    return empty_repo
