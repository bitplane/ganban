"""Handlers for 'ganban web' command."""

import shutil
import sys
from pathlib import Path

from textual_serve.server import Server

TEMPLATES_PATH = Path(__file__).resolve().parent.parent / "ui" / "web" / "templates"


def web(args) -> int:
    repo_path = str(Path(args.repo).resolve())

    ganban = shutil.which("ganban")
    if ganban is None:
        print("error: ganban not found on PATH", file=sys.stderr)
        return 1

    command = f"{ganban} {repo_path}"
    server = Server(
        command,
        host=args.host,
        port=args.port,
        title="ganban",
        templates_path=str(TEMPLATES_PATH),
    )

    print(f"serving {repo_path} at http://{args.host}:{args.port}")
    server.serve()
    return 0
