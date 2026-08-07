"""Handlers for 'ganban sync' command."""

import logging
import signal
import sys
import time
from pathlib import Path

from ganban.cli._common import output_json
from ganban.git import fetch_sync, get_remotes_sync, merge_order, push_sync, remote_has_branch, resolve_upstream
from ganban.model.loader import load_board
from ganban.model.writer import check_remote_for_merge, try_auto_merge

logger = logging.getLogger(__name__)


def _do_sync(repo_path: str) -> tuple[int, dict]:
    """Core sync logic. Returns (exit_code, result_dict).

    result_dict: {fetched: [], merged: [], pushed: str|None, error: str|None}
    """
    result = {"fetched": [], "merged": [], "pushed": None, "error": None}

    # Load board (verify ganban branch exists)
    try:
        board = load_board(repo_path, committers=False)
    except Exception as e:
        result["error"] = str(e)
        return 1, result

    # Get all remotes
    remotes = get_remotes_sync(repo_path)
    if not remotes:
        return 0, result

    upstream_remote = resolve_upstream(repo_path, remotes)

    # Fetch from ALL remotes
    for remote in remotes:
        try:
            fetch_sync(repo_path, remote)
            result["fetched"].append(remote)
        except Exception as e:
            logger.warning("fetch %s failed: %s", remote, e)

    board_stale = False
    for remote in merge_order(remotes, upstream_remote):
        if not remote_has_branch(repo_path, remote):
            continue

        # Reload only when a previous merge moved the branch
        if board_stale:
            board = load_board(repo_path, committers=False)
            board_stale = False

        merge_info = check_remote_for_merge(board, remote=remote)
        if merge_info is None:
            continue

        new_commit = try_auto_merge(board, merge_info, message=f"Merge {remote}/ganban")
        if new_commit is None:
            result["error"] = f"conflict merging {remote}/ganban"
            return 1, result
        result["merged"].append(remote)
        board_stale = True

    # Push to upstream
    try:
        push_sync(repo_path, upstream_remote)
        result["pushed"] = upstream_remote
    except Exception as e:
        logger.warning("push to %s failed: %s", upstream_remote, e)

    return 0, result


def sync(args) -> int:
    """One-shot sync handler. Dispatches to daemon if -d."""
    repo_path = str(Path(args.repo).resolve())

    if args.daemon:
        return sync_daemon(args, repo_path)

    exit_code, result = _do_sync(repo_path)

    if args.json:
        output_json(result)
    else:
        if result["fetched"]:
            print(f"fetched: {', '.join(result['fetched'])}")
        if result["merged"]:
            print(f"merged: {', '.join(result['merged'])}")
        if result["pushed"]:
            print(f"pushed: {result['pushed']}")
        if result["error"]:
            print(f"error: {result['error']}", file=sys.stderr)
        if not result["fetched"] and not result["merged"] and not result["pushed"] and not result["error"]:
            print("nothing to do")

    return exit_code


def sync_daemon(args, repo_path: str) -> int:
    """Loop _do_sync on interval. SIGINT/SIGTERM stops cleanly."""
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stderr,
        level=logging.INFO,
    )

    running = True

    def _stop(signum, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    interval = args.interval

    while running:
        exit_code, result = _do_sync(repo_path)
        if exit_code != 0:
            logger.error("sync failed: %s", result.get("error"))
        else:
            merged = result.get("merged", [])
            if merged:
                logger.info("merged: %s", ", ".join(merged))

        # Sleep in 1-second increments for responsive shutdown
        for _ in range(interval):
            if not running:
                break
            time.sleep(1)

    logger.info("stopped")
    return 0
