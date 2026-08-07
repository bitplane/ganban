"""Background sync engine for the TUI.

Runs: pull → load+merge → save → push, gated by board.git.sync toggles.
"""

import asyncio
import logging

from ganban.git import (
    fetch_sync,
    get_remotes_sync,
    get_upstream,
    push_sync,
    remote_has_branch,
)
from ganban.model.loader import load_board
from ganban.model.writer import (
    check_for_merge,
    check_remote_for_merge,
    save_board,
    try_auto_merge,
)

logger = logging.getLogger(__name__)


def apply_reload(board, new_board) -> None:
    """Apply a freshly loaded board in place, preserving live sync/config nodes."""
    sync_node = board.git.sync
    config_node = board.git.config
    board.update(new_board)
    board.git.sync = sync_node
    board.git.config = config_node


async def _merge_and_reload(board, merge_info, message) -> bool:
    """Run one auto-merge, then reload the board from the merge result.

    try_auto_merge builds "our" side from the in-memory board, so every
    merge must be applied back to the board before another merge runs —
    otherwise the next merge is computed from a stale tree and discards
    this one's changes. Returns False if the merge failed.
    """
    new_commit = await asyncio.to_thread(try_auto_merge, board, merge_info, message)
    if new_commit is None:
        return False
    board.commit = new_commit
    new_board = await asyncio.to_thread(load_board, board.repo_path)
    apply_reload(board, new_board)
    return True


async def run_sync_cycle(board):
    """Run one sync cycle: pull → save → merge → load → push.

    Reads board.git.sync.{local, remote} to decide which steps to run.
    Sets sync.status at each step (fires watchers → UI updates).
    All git I/O runs via asyncio.to_thread to stay non-blocking.
    """
    sync = board.git.sync
    config = board.git.config.ganban
    repo_path = board.repo_path
    do_local = config.sync_local
    do_remote = config.sync_remote

    try:
        # --- PULL (fetch from all remotes) ---
        remotes = []
        upstream_remote = None
        if do_remote:
            sync.status = "pull"
            remotes = await asyncio.to_thread(get_remotes_sync, repo_path)
            if remotes:
                upstream_info = await asyncio.to_thread(get_upstream, repo_path)
                if upstream_info:
                    upstream_remote = upstream_info[0]
                elif "origin" in remotes:
                    upstream_remote = "origin"
                else:
                    upstream_remote = remotes[0]

                for remote in remotes:
                    try:
                        await asyncio.to_thread(fetch_sync, repo_path, remote)
                    except Exception as exc:
                        logger.warning("fetch %s failed: %s", remote, exc)

        # --- SAVE (commit in-memory state to git) ---
        if do_local:
            sync.status = "save"
            new_commit = await asyncio.to_thread(save_board, board)
            board.commit = new_commit

        # --- MERGE (local divergence + remote branches) ---
        # The board is only reloaded when a merge brought in external
        # changes; otherwise the in-memory state is authoritative and
        # reloading risks overwriting user edits with a racy save snapshot.
        if do_local:
            sync.status = "load"

            # Local merge (another process may have committed)
            merge_info = await asyncio.to_thread(check_for_merge, board)
            if merge_info is not None:
                if not await _merge_and_reload(board, merge_info, "Auto-merge local changes"):
                    sync.status = "conflict"
                    return

            # Remote merges
            if do_remote and remotes:
                merge_order = [r for r in remotes if r != upstream_remote] + (
                    [upstream_remote] if upstream_remote else []
                )
                for remote in merge_order:
                    has_branch = await asyncio.to_thread(remote_has_branch, repo_path, remote)
                    if not has_branch:
                        continue
                    merge_info = await asyncio.to_thread(check_remote_for_merge, board, remote)
                    if merge_info is None:
                        continue
                    if not await _merge_and_reload(board, merge_info, f"Merge {remote}/ganban"):
                        sync.status = "conflict"
                        return

        # --- PUSH ---
        if do_remote and upstream_remote:
            sync.status = "push"
            try:
                await asyncio.to_thread(push_sync, repo_path, upstream_remote)
            except Exception as exc:
                logger.warning("push to %s failed: %s", upstream_remote, exc)

    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("sync cycle failed")
    finally:
        if sync.status != "conflict":
            sync.status = "idle"
