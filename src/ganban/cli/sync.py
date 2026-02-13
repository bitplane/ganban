"""Handlers for 'ganban sync' command."""

import logging
import signal
import sys
import time
from pathlib import Path

from ganban.cli._common import output_json
from ganban.git import fetch_sync, get_remotes_sync, get_upstream, push_sync, remote_has_branch
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
        board = load_board(repo_path)
    except Exception as e:
        result["error"] = str(e)
        return 1, result

    # Get all remotes
    remotes = get_remotes_sync(repo_path)
    if not remotes:
        return 0, result

    # Determine upstream
    upstream_info = get_upstream(repo_path)
    if upstream_info:
        upstream_remote = upstream_info[0]
    elif "origin" in remotes:
        upstream_remote = "origin"
    else:
        upstream_remote = remotes[0]

    # Fetch from ALL remotes
    for remote in remotes:
        try:
            fetch_sync(repo_path, remote)
            result["fetched"].append(remote)
        except Exception as e:
            logger.warning("fetch %s failed: %s", remote, e)

    # Merge order: non-upstream first, then upstream last
    merge_order = [r for r in remotes if r != upstream_remote] + [upstream_remote]

    for remote in merge_order:
        if not remote_has_branch(repo_path, remote):
            continue

        # Reload board for fresh commit after previous merge
        board = load_board(repo_path)

        merge_info = check_remote_for_merge(board, remote=remote)
        if merge_info is None:
            continue

        new_commit = try_auto_merge(board, merge_info, message=f"Merge {remote}/ganban")
        if new_commit is None:
            result["error"] = f"conflict merging {remote}/ganban"
            return 1, result
        result["merged"].append(remote)

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
