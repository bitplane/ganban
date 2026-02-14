"""Handlers for 'ganban web' command."""

import shutil
import sys
from pathlib import Path

from textual_serve.server import Server


def web(args) -> int:
    repo_path = str(Path(args.repo).resolve())

    ganban = shutil.which("ganban")
    if ganban is None:
        print("error: ganban not found on PATH", file=sys.stderr)
        return 1

    command = f"{ganban} {repo_path}"
    server = Server(command, host=args.host, port=args.port, title="ganban")

    print(f"serving {repo_path} at http://{args.host}:{args.port}")
    server.serve()
    return 0
