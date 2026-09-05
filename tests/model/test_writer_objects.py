"""Git object compatibility and process boundaries for board saves."""

import json
import os
import subprocess
import sys

import pytest
from git import Repo
from git.db import GitDB

from ganban.model.card import create_card
from ganban.model.column import create_column
from ganban.model.loader import load_board
from ganban.model.writer import _get_ref, _mktree, _update_tree, _write_blob, _write_commit, save_and_merge, save_board


@pytest.mark.parametrize("column_count", [1, 8])
@pytest.mark.parametrize("packed", [False, True])
@pytest.mark.parametrize("config_override", [False, True])
def test_save_process_budget(repo_with_ganban, monkeypatch, column_count, packed, config_override):
    """Observe real subprocess launches, including ones hidden by GitPython."""
    repo = Repo(repo_with_ganban)
    board = load_board(str(repo_with_ganban), committers=False)
    for index in range(2, column_count + 1):
        create_column(board, f"Column {index}", order=str(index))
    save_board(board)
    if packed:
        repo.git.gc()
        repo.git.pack_refs("--all", "--prune")
    if config_override:
        config = repo_with_ganban / "custom-gitconfig"
        config.write_text("[user]\n    name = Test writer\n    email = writer@example.test\n")
        monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))

    repo.git.checkout("--detach", repo.head.commit.hexsha)
    status_before = repo.git.status("--porcelain")
    index_before = (repo_with_ganban / ".git" / "index").read_bytes()
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import json
import sys
from ganban.model.card import create_card
from ganban.model.loader import load_board
from ganban.model.writer import save_and_merge

board = load_board(sys.argv[1], committers=False)
commands = []
def audit(event, args):
    if event == 'subprocess.Popen':
        commands.append(args[1])
sys.addaudithook(audit)

save_and_merge(board)
unchanged = commands[:]
commands.clear()
create_card(board, 'Another card', 'Body.')
commit, merged = save_and_merge(board)
print(json.dumps({'unchanged': unchanged, 'changed': commands, 'commit': commit, 'merged': merged}))
""",
            str(repo_with_ganban),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    observed = json.loads(result.stdout)
    assert observed["unchanged"] == []
    expected = [["git", "commit-tree"]] if config_override else []
    expected.append(["git", "update-ref"])
    assert [command[:2] for command in observed["changed"]] == expected
    assert observed["merged"] is False
    assert repo.commit("ganban").hexsha == observed["commit"]
    assert len(load_board(str(repo_with_ganban), committers=False).cards) == 2
    assert (repo_with_ganban / ".git" / "index").read_bytes() == index_before
    assert repo.git.status("--porcelain") == status_before
    repo.git.fsck("--no-dangling")


def test_tree_matches_git_mktree(empty_repo):
    """Tree encoding matches Git's modes, byte ordering, and filename handling."""
    repo = Repo(empty_repo, odbt=GitDB)
    blob = _write_blob(repo, "content\n")
    link = _write_blob(repo, "../.all/001.md")
    empty_tree = _mktree(repo, [])
    entries = [
        ("040000", "tree", empty_tree, "foo"),
        ("100644", "blob", blob, "foo.bar"),
        ("100755", "blob", blob, "foo0"),
        ("100644", "blob", blob, "héllo ✓"),
        ("120000", "blob", link, 'link\twith\n"quotes"'),
    ]
    result = subprocess.run(
        ["git", "mktree", "-z"],
        cwd=empty_repo,
        input=b"".join(f"{mode} {kind} {sha}\t{name}\0".encode() for mode, kind, sha, name in entries),
        capture_output=True,
        check=True,
    )
    assert _mktree(repo, entries) == result.stdout.decode().strip()
    assert empty_tree == "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


@pytest.mark.parametrize("message", ["", "Save board", "Unicode ✓\n\nDetails", "Already terminated\n", "Extra\n\n"])
@pytest.mark.parametrize("parent_count", [0, 1, 2])
def test_commit_matches_git_commit_tree(empty_repo, monkeypatch, message, parent_count):
    """Commit serialization preserves identity, dates, messages, and parents."""
    repo = Repo(empty_repo, odbt=GitDB)
    for key, value in {
        "GIT_AUTHOR_NAME": "Author ✓",
        "GIT_AUTHOR_EMAIL": "author@example.test",
        "GIT_COMMITTER_NAME": "Committer",
        "GIT_COMMITTER_EMAIL": "committer@example.test",
        "GIT_AUTHOR_DATE": "2001-02-03T04:05:06 +0530",
        "GIT_COMMITTER_DATE": "2002-03-04T05:06:07 -0230",
    }.items():
        monkeypatch.setenv(key, value)
    tree = _mktree(repo, [])
    parents = [repo.head.commit.hexsha, _write_commit(repo, tree, [], "Other parent")][:parent_count]
    parent_args = [arg for parent in parents for arg in ("-p", parent)]
    expected = subprocess.run(
        ["git", "commit-tree", tree, *parent_args, "-m", message],
        cwd=empty_repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert _write_commit(repo, tree, parents, message) == expected


def test_ref_reads_follow_symbolic_and_packed_refs(empty_repo):
    repo = Repo(empty_repo)
    sha = repo.head.commit.hexsha
    repo.git.update_ref("refs/heads/board", sha)
    repo.git.symbolic_ref("refs/heads/alias", "refs/heads/board")
    repo.git.pack_refs("--all", "--prune")
    assert _get_ref(empty_repo, "refs/heads/board") == sha
    assert _get_ref(empty_repo, "refs/heads/alias") == sha
    assert _get_ref(empty_repo, "refs/heads/missing") is None


@pytest.mark.parametrize("date", ["@981153306 +0530", "Sat, 03 Feb 2001 04:05:06 +0530", "2001.02.03 04:05:06 +0530"])
def test_commit_date_formats_match_git(empty_repo, monkeypatch, date):
    repo = Repo(empty_repo, odbt=GitDB)
    monkeypatch.setenv("GIT_AUTHOR_DATE", date)
    monkeypatch.setenv("GIT_COMMITTER_DATE", date)
    tree = _mktree(repo, [])
    expected = repo.git.commit_tree(tree, "-m", "Date formats")
    assert _write_commit(repo, tree, [], "Date formats") == expected


def test_commit_uses_configured_identities(empty_repo, monkeypatch):
    repo = Repo(empty_repo, odbt=GitDB)
    for role in ("AUTHOR", "COMMITTER"):
        for field in ("NAME", "EMAIL"):
            monkeypatch.delenv(f"GIT_{role}_{field}", raising=False)
        monkeypatch.setenv(f"GIT_{role}_DATE", "1000000000 +0000")
    with repo.config_writer() as config:
        config.set_value("author", "name", "Configured author")
        config.set_value("author", "email", "author@example.test")
        config.set_value("committer", "name", "Configured committer")
        config.set_value("committer", "email", "committer@example.test")
    tree = _mktree(repo, [])
    expected = repo.git.commit_tree(tree, "-m", "Configured identities")
    assert _write_commit(repo, tree, [], "Configured identities") == expected


def test_commit_respects_git_config_environment(empty_repo, monkeypatch):
    """Custom Git configuration must not silently use GitPython's defaults."""
    repo = Repo(empty_repo, odbt=GitDB)
    tree = _mktree(repo, [])
    config = empty_repo / "custom-gitconfig"
    config.write_text("[user]\n    name = Custom author\n    email = custom@example.test\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", os.devnull)
    for role in ("AUTHOR", "COMMITTER"):
        for field in ("NAME", "EMAIL"):
            monkeypatch.delenv(f"GIT_{role}_{field}", raising=False)
        monkeypatch.setenv(f"GIT_{role}_DATE", "1000000000 +0000")
    expected = repo.git.commit_tree(tree, "-m", "Custom config")
    assert _write_commit(repo, tree, [], "Custom config") == expected
    assert repo.commit(expected).author.email == "custom@example.test"

    config.write_text("[user]\n    useConfigOnly = true\n")
    with pytest.raises(subprocess.CalledProcessError):
        _write_commit(repo, tree, [], "Missing required identity")


@pytest.mark.parametrize("kind", ["bare", "worktree"])
def test_save_in_bare_repo_and_linked_worktree(repo_with_ganban, tmp_path, kind):
    source = Repo(repo_with_ganban)
    with source.config_writer() as config:
        config.set_value("author", "name", "Repository author")
        config.set_value("author", "email", "repository@example.test")
    target = tmp_path / "other"
    if kind == "bare":
        repo = Repo.clone_from(str(repo_with_ganban), target, bare=True)
    else:
        source.git.worktree("add", "--detach", str(target), "ganban")
        repo = Repo(target)
    board = load_board(str(target), committers=False)
    create_card(board, "Saved from another repository layout")
    commit, merged = save_and_merge(board)
    assert not merged
    assert repo.commit("ganban").hexsha == commit
    if kind == "worktree":
        assert repo.commit(commit).author.email == "repository@example.test"
    assert len(load_board(str(target), committers=False).cards) == 2
    repo.git.fsck("--no-dangling")


def test_update_tree_matches_git_index(empty_repo):
    """Edits, deletes, modes, unusual names, and untouched trees match Git."""
    repo = Repo(empty_repo, odbt=GitDB)
    blob = _write_blob(repo, "old\n")
    new_blob = _write_blob(repo, "new\n")
    subtree = _mktree(repo, [("100755", "blob", blob, "file")])
    tree = _mktree(repo, [("040000", "tree", subtree, name) for name in ("keep", "delete", "edit")])
    changes = {
        "delete/file": None,
        "edit/file": ("100644", new_blob),
        'new/nested/link\twith\n"quotes"': ("120000", blob),
    }
    env = {**os.environ, "GIT_INDEX_FILE": str(empty_repo / "test-index")}
    subprocess.run(["git", "read-tree", tree], cwd=empty_repo, env=env, check=True)
    for path, value in changes.items():
        args = ["--force-remove", path] if value is None else ["--add", "--cacheinfo", f"{value[0]},{value[1]},{path}"]
        subprocess.run(["git", "update-index", *args], cwd=empty_repo, env=env, check=True)
    expected = subprocess.run(
        ["git", "write-tree"], cwd=empty_repo, env=env, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert _update_tree(empty_repo, tree, changes) == expected


def test_concurrent_processes_preserve_both_cards(repo_with_ganban):
    """Two writers start from the same snapshot and race to publish their cards."""
    script = """
import sys
from ganban.model.card import create_card
from ganban.model.loader import load_board
from ganban.model.writer import save_and_merge
board = load_board(sys.argv[1], committers=False)
create_card(board, sys.argv[2])
print('ready', flush=True)
sys.stdin.readline()
commit, merged = save_and_merge(board)
print(commit, flush=True)
"""
    writers = []
    try:
        for title in ("Writer A", "Writer B"):
            writers.append(
                subprocess.Popen(
                    [sys.executable, "-c", script, str(repo_with_ganban), title],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
            )
        for writer in writers:
            assert writer.stdout.readline().strip() == "ready"
        for writer in writers:
            writer.stdin.write("save\n")
            writer.stdin.flush()
        for writer in writers:
            stdout, stderr = writer.communicate(timeout=30)
            assert writer.returncode == 0, stderr
            assert len(stdout.strip()) == 40
    finally:
        for writer in writers:
            if writer.poll() is None:
                writer.kill()
            writer.communicate()

    board = load_board(str(repo_with_ganban), committers=False)
    titles = {card.sections.keys()[0] for card in board.cards}
    assert titles == {"First card", "Writer A", "Writer B"}
    Repo(repo_with_ganban).git.fsck("--no-dangling")
