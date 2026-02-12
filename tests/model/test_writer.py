"""Tests for the Node-tree board writer."""

import tempfile
from pathlib import Path

import pytest
from git import Repo

from ganban.model.card import create_card
from ganban.model.column import create_column, slugify
from ganban.model.loader import load_board
from ganban.model.node import ListNode, Node
from ganban.model.writer import (
    MergeRequired,
    _meta_to_dict,
    check_for_merge,
    check_remote_for_merge,
    save_board,
    try_auto_merge,
)

from .conftest import _make_board, _make_card, _make_column


# --- Save tests ---


def test_save_new_board(empty_repo):
    """Save a board to a fresh repo creates the branch."""
    board = _make_board(
        empty_repo,
        cards={"001": _make_card("Test card", "Body text.")},
        columns=[_make_column("1", "Backlog", links=["001"])],
    )

    new_commit = save_board(board, message="Create board")
    assert len(new_commit) == 40

    loaded = load_board(str(empty_repo))
    assert len(loaded.cards) == 1
    assert loaded.cards["1"] is not None
    assert loaded.cards["1"].sections["Test card"] == "Body text."
    assert len(loaded.columns) == 1
    assert loaded.columns["1"].links == ["1"]


def test_save_updates_existing_board(repo_with_ganban):
    """Save modifications to an existing board."""
    board = load_board(str(repo_with_ganban))
    original_commit = board.commit

    # Add a new card
    new_sections = ListNode()
    new_sections["New card"] = "New description."
    board.cards["2"] = Node(sections=new_sections, meta={})

    # Add a new column with the card
    col = _make_column("2", "Done", links=["2"])
    board.columns["2"] = col

    new_commit = save_board(board, message="Add card and column")
    assert new_commit != original_commit

    repo = Repo(repo_with_ganban)
    commit = repo.commit(new_commit)
    assert commit.parents[0].hexsha == original_commit


def test_save_board_with_root_index(empty_repo):
    """Board with root index.md is saved correctly."""
    sections = ListNode()
    sections["My Board"] = "Board description."

    board = _make_board(
        empty_repo,
        cards={"001": _make_card("Card")},
        columns=[_make_column("1", "Backlog")],
        sections=sections,
    )

    save_board(board)

    loaded = load_board(str(empty_repo))
    assert loaded.sections["My Board"] == "Board description."


def test_save_board_with_column_index(empty_repo):
    """Column with index.md is saved correctly."""
    col_sections = ListNode()
    col_sections["Backlog"] = "Column description."

    board = _make_board(
        empty_repo,
        cards={"001": _make_card("Card")},
        columns=[_make_column("1", "Backlog", sections=col_sections)],
    )

    save_board(board)

    loaded = load_board(str(empty_repo))
    col = loaded.columns["1"]
    assert col.sections["Backlog"] == "Column description."


def test_save_preserves_card_metadata(empty_repo):
    """Card front-matter is preserved through save/load cycle."""
    board = _make_board(
        empty_repo,
        cards={"001": _make_card("Urgent card", "Fix this ASAP.", meta={"tags": ["urgent", "bug"], "priority": 1})},
        columns=[_make_column("1", "Backlog")],
    )

    save_board(board)

    loaded = load_board(str(empty_repo))
    card_meta = loaded.cards["1"].meta
    assert card_meta.tags == ["urgent", "bug"]
    assert card_meta.priority == 1


def test_save_move_card_between_columns(repo_with_ganban):
    """Moving a card between columns shows up correctly."""
    board = load_board(str(repo_with_ganban))

    # Move card from backlog to a new done column
    backlog = board.columns["1"]
    card_id = backlog.links[0]
    backlog.links = []

    col = _make_column("2", "Done", links=[card_id])
    board.columns["2"] = col

    save_board(board, message="Move card to done")

    loaded = load_board(str(repo_with_ganban))
    assert loaded.columns["1"].links == []
    assert loaded.columns["2"].links == ["1"]


def test_save_delete_card(repo_with_ganban):
    """Deleting a card removes it from .all/"""
    board = load_board(str(repo_with_ganban))
    assert board.cards["1"] is not None

    # Remove card and its link
    board.cards["1"] = None
    backlog = board.columns["1"]
    backlog.links = []

    save_board(board, message="Delete card")

    loaded = load_board(str(repo_with_ganban))
    assert loaded.cards["1"] is None


def test_save_reorder_cards_in_column(empty_repo):
    """Reordering cards updates their position prefixes."""
    board = _make_board(
        empty_repo,
        cards={
            "001": _make_card("First"),
            "002": _make_card("Second"),
            "003": _make_card("Third"),
        },
        columns=[_make_column("1", "Backlog", links=["001", "002", "003"])],
    )

    save_board(board)

    # Reorder: move third to first position
    loaded = load_board(str(empty_repo))
    backlog = loaded.columns["1"]
    backlog.links = ["3", "1", "2"]

    save_board(loaded, message="Reorder cards")

    reloaded = load_board(str(empty_repo))
    assert reloaded.columns["1"].links == ["3", "1", "2"]


def test_save_empty_column(empty_repo):
    """Empty columns are saved correctly."""
    board = _make_board(
        empty_repo,
        cards={},
        columns=[
            _make_column("1", "Backlog"),
            _make_column("2", "Done"),
        ],
    )

    save_board(board)

    loaded = load_board(str(empty_repo))
    assert len(loaded.columns) == 2
    for col in loaded.columns:
        assert col.links == []


def test_save_returns_valid_commit(empty_repo):
    """The returned commit hash is valid and points to correct tree."""
    board = _make_board(
        empty_repo,
        cards={"001": _make_card("Test")},
        columns=[_make_column("1", "Backlog")],
    )

    commit_sha = save_board(board)

    repo = Repo(empty_repo)
    commit = repo.commit(commit_sha)
    assert commit.message.strip() == "Update board"
    assert ".all" in commit.tree
    assert "1.backlog" in commit.tree


def test_save_custom_branch(empty_repo):
    """Can save to a custom branch name."""
    board = _make_board(
        empty_repo,
        cards={"001": _make_card("Test")},
        columns=[_make_column("1", "Backlog")],
    )

    save_board(board, branch="my-board")

    with pytest.raises(ValueError, match="Branch 'ganban' not found"):
        load_board(str(empty_repo))

    loaded = load_board(str(empty_repo), branch="my-board")
    assert loaded.cards["1"] is not None


def test_save_custom_message(empty_repo):
    """save_board with a custom message produces that commit message."""
    board = _make_board(
        empty_repo,
        cards={"001": _make_card("Test")},
        columns=[_make_column("1", "Backlog")],
    )

    commit_sha = save_board(board, message="Add card: Test")

    repo = Repo(empty_repo)
    commit = repo.commit(commit_sha)
    assert commit.message.strip() == "Add card: Test"


def test_save_noop_skips_commit(repo_with_ganban):
    """Saving an unchanged board returns the same commit, no new history."""
    # First save to normalize the tree (adds index.md etc.)
    board = load_board(str(repo_with_ganban))
    baseline_commit = save_board(board, message="Normalize")

    # Reload from the normalized state
    board = load_board(str(repo_with_ganban))
    assert board.commit == baseline_commit

    repo = Repo(repo_with_ganban)
    commits_before = list(repo.iter_commits("ganban"))

    result = save_board(board, message="Should not appear")

    assert result == baseline_commit

    commits_after = list(repo.iter_commits("ganban"))
    assert len(commits_after) == len(commits_before)


def test_save_with_explicit_parents(repo_with_ganban):
    """Can save with explicit parent commits for merge."""
    board = load_board(str(repo_with_ganban))
    first_commit = board.commit

    # Make a change and save
    board.cards["1"].sections["First card"] = "Changed"
    second_commit = save_board(board)

    # Now create a "merge" commit with both as parents
    board = load_board(str(repo_with_ganban))
    board.cards["1"].sections["First card"] = "Merged"
    merge_commit = save_board(board, message="Merge", parents=[first_commit, second_commit])

    repo = Repo(repo_with_ganban)
    commit = repo.commit(merge_commit)
    assert len(commit.parents) == 2


# --- Merge detection tests ---


def test_check_for_merge_no_changes(repo_with_ganban):
    """No merge needed when branch hasn't moved."""
    board = load_board(str(repo_with_ganban))
    assert check_for_merge(board) is None


def test_check_for_merge_branch_moved(repo_with_ganban):
    """Merge needed when branch has moved."""
    board = load_board(str(repo_with_ganban))
    original_commit = board.commit

    # External change moves the branch
    repo = Repo(repo_with_ganban)
    repo.git.checkout("ganban")
    all_dir = repo_with_ganban / ".all"
    (all_dir / "002.md").write_text("# External card\n")
    repo.git.add("-A")
    external_commit = repo.index.commit("External change").hexsha

    result = check_for_merge(board)

    assert result is not None
    assert isinstance(result, MergeRequired)
    assert result.ours == original_commit
    assert result.theirs == external_commit
    assert result.base == original_commit


def test_check_for_merge_new_branch(empty_repo):
    """No merge needed for new branch."""
    board = _make_board(
        empty_repo,
        cards={"001": _make_card("Test")},
        columns=[_make_column("1", "Backlog")],
    )
    assert check_for_merge(board) is None


def test_check_for_merge_no_board_commit(repo_with_ganban):
    """No merge check when board has no commit (fresh board)."""
    board = Node(repo_path=str(repo_with_ganban))
    assert check_for_merge(board) is None


def test_check_for_merge_unrelated_histories(repo_with_ganban):
    """No merge when histories have no common ancestor."""
    board = load_board(str(repo_with_ganban))

    repo = Repo(repo_with_ganban)
    repo.git.checkout("--orphan", "unrelated")
    repo.git.rm("-rf", ".", "--cached")
    repo.git.clean("-fd")

    all_dir = repo_with_ganban / ".all"
    all_dir.mkdir()
    (all_dir / "999.md").write_text("# Unrelated card\n")
    backlog = repo_with_ganban / "1.backlog"
    backlog.mkdir()

    repo.git.add("-A")
    repo.index.commit("Unrelated commit")

    unrelated_commit = repo.head.commit.hexsha
    repo.git.update_ref("refs/heads/ganban", unrelated_commit)

    assert check_for_merge(board) is None


# --- Auto-merge tests ---


def test_auto_merge_clean(repo_with_ganban):
    """Auto-merge succeeds when different files changed."""
    board = load_board(str(repo_with_ganban))
    original_commit = board.commit

    # External change: add new card
    repo = Repo(repo_with_ganban)
    repo.git.checkout("ganban")
    all_dir = repo_with_ganban / ".all"
    (all_dir / "002.md").write_text("# External card\n\nAdded externally.\n")
    repo.git.add("-A")
    external_commit = repo.index.commit("Add external card").hexsha

    # Our change: edit card 001
    board.cards["1"].sections["First card"] = "Modified description."

    merge_info = check_for_merge(board)
    assert merge_info is not None

    new_commit = try_auto_merge(board, merge_info, message="Auto-merge")
    assert new_commit is not None

    commit = repo.commit(new_commit)
    assert len(commit.parents) == 2
    parent_shas = {p.hexsha for p in commit.parents}
    assert original_commit in parent_shas
    assert external_commit in parent_shas

    loaded = load_board(str(repo_with_ganban))
    assert loaded.cards["1"].sections["First card"] == "Modified description."
    assert loaded.cards["2"] is not None


def test_auto_merge_conflict_theirs_wins(repo_with_ganban):
    """Conflict resolved by most-recent-commit-wins (theirs is newer)."""
    board = load_board(str(repo_with_ganban))

    # External change: edit card 001 (committed after our load, so newer)
    repo = Repo(repo_with_ganban)
    repo.git.checkout("ganban")
    all_dir = repo_with_ganban / ".all"
    (all_dir / "001.md").write_text("# First card\n\nExternal edit.\n")
    repo.git.add("-A")
    repo.index.commit("External edit")

    # Our change: also edit card 001
    board.cards["1"].sections["First card"] = "Our edit."

    merge_info = check_for_merge(board)
    assert merge_info is not None

    result = try_auto_merge(board, merge_info)
    assert result is not None

    # Theirs is newer, so their content wins
    repo.git.checkout("ganban")
    loaded = load_board(str(repo_with_ganban))
    assert loaded.cards["1"].sections["First card"] == "External edit."

    # Merge commit has both parents
    commit = repo.commit(result)
    assert len(commit.parents) == 2


def test_auto_merge_conflict_ours_wins(repo_with_ganban):
    """Conflict resolved by most-recent-commit-wins (ours is newer)."""
    board = load_board(str(repo_with_ganban))

    # External change: edit card 001 with an old timestamp
    repo = Repo(repo_with_ganban)
    repo.git.checkout("ganban")
    all_dir = repo_with_ganban / ".all"
    (all_dir / "001.md").write_text("# First card\n\nExternal edit.\n")
    repo.git.add("-A")
    # Commit with a very old date so ours wins
    repo.git.commit("-m", "External edit", date="2000-01-01T00:00:00")

    # Our change: also edit card 001
    board.cards["1"].sections["First card"] = "Our edit."

    # Save our board so it gets a fresh (newer) commit
    save_board(board)

    merge_info = check_for_merge(board)
    assert merge_info is not None

    result = try_auto_merge(board, merge_info)
    assert result is not None

    # Ours is newer, so our content wins
    loaded = load_board(str(repo_with_ganban))
    assert loaded.cards["1"].sections["First card"] == "Our edit."

    commit = repo.commit(result)
    assert len(commit.parents) == 2


def test_auto_merge_conflict_preserves_clean_changes(repo_with_ganban):
    """Conflict resolution preserves non-conflicting changes from both sides."""
    board = load_board(str(repo_with_ganban))

    # External change: edit card 001 AND card 002
    repo = Repo(repo_with_ganban)
    repo.git.checkout("ganban")
    all_dir = repo_with_ganban / ".all"
    (all_dir / "001.md").write_text("# First card\n\nExternal edit.\n")
    (all_dir / "002.md").write_text("# Second card\n\nTheir non-conflicting edit.\n")
    repo.git.add("-A")
    repo.index.commit("External edits")

    # Our change: only edit card 001 (conflicts) — card 002 untouched by us
    board.cards["1"].sections["First card"] = "Our edit."

    merge_info = check_for_merge(board)
    result = try_auto_merge(board, merge_info)
    assert result is not None

    loaded = load_board(str(repo_with_ganban))
    # Card 002 should have their non-conflicting edit preserved
    assert loaded.cards["2"].sections["Second card"] == "Their non-conflicting edit."


# --- Remote merge tests ---


@pytest.fixture
def repo_with_remote(tmp_path):
    """Create a repo with a ganban branch and a 'remote' repo."""
    remote_path = tmp_path / "remote.git"
    Repo.init(remote_path, bare=True)

    local_path = tmp_path / "local"
    local_path.mkdir()
    local_repo = Repo.init(local_path)

    (local_path / ".gitkeep").write_text("")
    local_repo.index.add([".gitkeep"])
    local_repo.index.commit("Initial commit")

    local_repo.git.checkout("--orphan", "ganban")
    local_repo.git.rm("-rf", ".", "--cached")
    local_repo.git.clean("-fd")

    all_dir = local_path / ".all"
    all_dir.mkdir()
    (all_dir / "001.md").write_text("# First card\n\nDescription.\n")

    backlog = local_path / "1.backlog"
    backlog.mkdir()
    (backlog / "01.first-card.md").symlink_to("../.all/001.md")

    local_repo.git.add("-A")
    local_repo.index.commit("Initial board")

    local_repo.create_remote("origin", str(remote_path))
    local_repo.git.push("origin", "ganban")

    return local_path, remote_path


def test_check_remote_no_changes(repo_with_remote):
    """No merge needed when remote hasn't changed."""
    local_path, _ = repo_with_remote
    board = load_board(str(local_path))
    assert check_remote_for_merge(board, remote="origin") is None


def test_check_remote_no_board_commit(repo_with_remote):
    """No merge check when board has no commit."""
    local_path, _ = repo_with_remote
    board = Node(repo_path=str(local_path))
    assert check_remote_for_merge(board, remote="origin") is None


def test_check_remote_tracking_branch_missing(repo_with_ganban):
    """No merge when remote tracking branch doesn't exist."""
    board = load_board(str(repo_with_ganban))
    assert check_remote_for_merge(board, remote="origin") is None


def test_check_remote_unrelated_histories(repo_with_remote):
    """No merge when remote has unrelated history."""
    local_path, remote_path = repo_with_remote
    board = load_board(str(local_path))

    with tempfile.TemporaryDirectory() as other_path:
        other_repo = Repo.init(other_path)

        all_dir = Path(other_path) / ".all"
        all_dir.mkdir()
        (all_dir / "999.md").write_text("# Unrelated\n")
        backlog = Path(other_path) / "1.backlog"
        backlog.mkdir()
        (backlog / ".gitkeep").write_text("")

        other_repo.git.add("-A")
        other_repo.index.commit("Unrelated history")

        other_repo.create_remote("origin", str(remote_path))
        other_repo.git.push("origin", "HEAD:ganban", "--force")

    local_repo = Repo(local_path)
    local_repo.remotes.origin.fetch()

    assert check_remote_for_merge(board, remote="origin") is None


def test_check_remote_has_changes(repo_with_remote):
    """Merge needed when remote has new commits."""
    local_path, remote_path = repo_with_remote
    board = load_board(str(local_path))
    original_commit = board.commit

    with tempfile.TemporaryDirectory() as other_path:
        other_repo = Repo.clone_from(str(remote_path), other_path)
        other_repo.git.checkout("ganban")

        all_dir = Path(other_path) / ".all"
        (all_dir / "002.md").write_text("# Remote card\n\nAdded by someone else.\n")
        other_repo.git.add("-A")
        other_repo.index.commit("Add card from remote")
        other_repo.git.push("origin", "ganban")

    local_repo = Repo(local_path)
    local_repo.remotes.origin.fetch()

    result = check_remote_for_merge(board, remote="origin")

    assert result is not None
    assert isinstance(result, MergeRequired)
    assert result.ours == original_commit
    assert result.theirs != original_commit
    assert result.base == original_commit


def test_check_remote_we_are_ahead(repo_with_remote):
    """No merge needed when we are ahead of remote."""
    local_path, _ = repo_with_remote
    board = load_board(str(local_path))

    board.cards["1"].sections["First card"] = "Local change."
    save_board(board)

    board = load_board(str(local_path))
    assert check_remote_for_merge(board, remote="origin") is None


def test_remote_auto_merge(repo_with_remote):
    """Full flow: fetch, check, auto-merge from remote."""
    local_path, remote_path = repo_with_remote
    board = load_board(str(local_path))

    board.cards["1"].sections["First card"] = "Local edit."

    with tempfile.TemporaryDirectory() as other_path:
        other_repo = Repo.clone_from(str(remote_path), other_path)
        other_repo.git.checkout("ganban")

        all_dir = Path(other_path) / ".all"
        (all_dir / "002.md").write_text("# Remote card\n")
        other_repo.git.add("-A")
        other_repo.index.commit("Add card from remote")
        other_repo.git.push("origin", "ganban")

    local_repo = Repo(local_path)
    local_repo.remotes.origin.fetch()

    merge_info = check_remote_for_merge(board, remote="origin")
    assert merge_info is not None

    new_commit = try_auto_merge(board, merge_info, message="Merge remote")
    assert new_commit is not None

    loaded = load_board(str(local_path))
    assert loaded.cards["1"].sections["First card"] == "Local edit."
    assert loaded.cards["2"] is not None


# --- create_card tests ---


def test_create_card_basic(repo_with_ganban):
    """Create a card with default options."""
    board = load_board(str(repo_with_ganban))
    original_count = len(board.cards)

    card_id, card = create_card(board, "New card", "Description here")

    assert card is not None
    assert card_id == "2"  # next_id after "1" is "2"
    assert "New card" in card.sections.keys()
    assert len(board.cards) == original_count + 1

    # Should be added to first column's links
    backlog = board.columns["1"]
    assert backlog.links[-1] == "2"


def test_create_card_empty_board(empty_repo):
    """Create a card on an empty board."""
    board = _make_board(
        empty_repo,
        columns=[_make_column("1", "Backlog")],
    )

    card_id, card = create_card(board, "First card")

    assert card is not None
    assert card_id == "1"
    assert board.cards["1"] is not None
    assert board.columns["1"].links == ["1"]


def test_create_card_saves(repo_with_ganban):
    """Created cards persist after save."""
    board = load_board(str(repo_with_ganban))

    card_id, card = create_card(board, "Persistent card", "Will be saved")
    save_board(board)

    loaded = load_board(str(repo_with_ganban))
    assert loaded.cards[card_id] is not None
    assert loaded.cards[card_id].sections["Persistent card"] == "Will be saved"


# --- create_column tests ---


def test_create_column_basic(repo_with_ganban):
    """Create a column with default order."""
    board = load_board(str(repo_with_ganban))
    original_count = len(board.columns)

    column = create_column(board, "Archive")

    assert column.sections.keys()[0] == "Archive"
    assert column.order == "2"
    assert column.dir_path == "2.archive"
    assert column.hidden is False
    assert len(board.columns) == original_count + 1


def test_create_column_hidden(repo_with_ganban):
    """Create a hidden column."""
    board = load_board(str(repo_with_ganban))

    column = create_column(board, "Hidden", hidden=True)

    assert column.hidden is True
    assert column.dir_path.startswith(".")


def test_create_column_empty_board(empty_repo):
    """Create first column on empty board."""
    board = _make_board(empty_repo)

    column = create_column(board, "Backlog")

    assert column.order == "1"
    assert len(board.columns) == 1


def test_create_column_saves(repo_with_ganban):
    """Created columns persist after save."""
    board = load_board(str(repo_with_ganban))

    create_column(board, "Archive")
    save_board(board)

    loaded = load_board(str(repo_with_ganban))
    names = [col.sections.keys()[0] for col in loaded.columns]
    assert "Archive" in names


# --- slugify tests ---


def test_meta_to_dict_recursive():
    """Nested Node children are serialized to plain dicts."""

    meta = Node(
        simple="value",
        nested={"inner_key": "inner_value", "deep": {"level3": 42}},
        number=99,
    )
    result = _meta_to_dict(meta)
    assert result == {
        "simple": "value",
        "nested": {"inner_key": "inner_value", "deep": {"level3": 42}},
        "number": 99,
    }
    # Verify nested values are plain dicts, not Nodes
    assert type(result["nested"]) is dict
    assert type(result["nested"]["deep"]) is dict


def test_meta_to_dict_preserves_flat():
    """Non-nested meta round-trips correctly."""

    meta = Node(tags=["a", "b"], priority=1)
    result = _meta_to_dict(meta)
    assert result == {"tags": ["a", "b"], "priority": 1}


def test_meta_to_dict_empty():
    """Empty Node returns empty dict."""

    assert _meta_to_dict(Node()) == {}
    assert _meta_to_dict({}) == {}
    assert _meta_to_dict(None) == {}


def test_slugify_basic():
    assert slugify("Hello World") == "hello-world"


def test_slugify_special_chars():
    assert slugify("What: is this?") == "what-is-this"
    assert slugify("Test!") == "test"
    assert slugify("{foo}") == "foo"
    assert slugify("a.b.c") == "a-b-c"


def test_slugify_multiple_spaces():
    assert slugify("hello    world") == "hello-world"
    assert slugify("a - b - c") == "a-b-c"


def test_slugify_leading_trailing():
    assert slugify("  hello  ") == "hello"
    assert slugify("---test---") == "test"
    assert slugify("!hello!") == "hello"


def test_slugify_empty():
    assert slugify("") == "untitled"
    assert slugify("   ") == "untitled"
    assert slugify("!!!") == "untitled"
