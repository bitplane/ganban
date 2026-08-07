# AGENTS.md

Guidance for AI agents working on this codebase. Read this first — it'll save
you a lot of token-burning exploration.

## Overview

ganban is a git-based kanban board. The board lives on an orphan branch
(`ganban`) as plain markdown files. It has a Textual TUI, a CLI, and the data
layer uses git plumbing (no working tree checkout). Python 3.11+, built with
flit.

## Project structure

```
src/ganban/
├── __main__.py          # Entry: no args → TUI, subcommand → CLI
├── model/               # Core data model (reactive Node tree)
│   ├── node.py          # Node (dict-like) and ListNode (ordered, id-keyed), clone()
│   ├── loader.py        # Load board from git branch into Node tree
│   ├── writer.py        # Save Node tree back to git; CAS ref updates, save_and_merge
│   ├── board.py         # Board-level helpers (default board scaffold)
│   ├── card.py          # Card mutations: create, move, archive; label ops
│   └── column.py        # Column mutations: create, move, rename, archive
├── cli/                 # Argparse CLI
│   ├── __init__.py      # Parser & dispatch (noun-verb pattern)
│   ├── _common.py       # Shared helpers: load, save, output
│   ├── board.py         # board summary/get/set
│   ├── card.py          # card list/get/set/add/move/archive
│   ├── column.py        # column list/get/set/add/move/rename/archive
│   ├── init.py          # ganban init
│   ├── sync.py          # ganban sync (one-shot or -d daemon)
│   └── web.py           # ganban web (serve the TUI in a browser)
├── ui/                  # Textual TUI
│   ├── app.py           # GanbanApp, screen routing
│   ├── board.py         # BoardScreen (main screen, column reconciliation)
│   ├── column.py        # ColumnWidget
│   ├── card.py          # CardWidget
│   ├── card_indicators.py  # Pure footer/header indicator builders
│   ├── watcher.py       # NodeWatcherMixin (reactive watch + suppression)
│   ├── drag.py          # DraggableMixin + DropTarget
│   ├── detail.py        # Modal detail screens
│   ├── menu.py          # Context menus (+ truncate helper for titles)
│   ├── tag.py           # Tag widget + TagListWidget base (labels/deps editors)
│   └── edit/            # Editable widgets, section editors, AddValueMixin
├── git.py               # Async git wrappers (GitPython + asyncio.to_thread)
├── sync.py              # Background sync engine for the TUI (save/merge/reload)
├── ids.py               # ID comparison & generation (zero-padded, extensible)
└── parser.py            # Markdown ↔ sections + YAML front-matter
```

## Data model

Board data is stored on an orphan git branch as markdown files:

```
ganban/              (branch root)
├── index.md         board metadata
├── .all/            card store (canonical copies)
│   ├── 001.md
│   └── 002.md
└── 1.backlog/       columns (N.slug naming = sort order)
    ├── index.md     column metadata
    ├── 01.card.md   symlink → ../.all/001.md
    └── 02.card.md   symlink → ../.all/002.md
```

Cards are markdown with optional YAML front-matter. Sections are split by `#`
headings. The parser round-trips cleanly.

### Reactive Node tree

`Node` (dict-like) and `ListNode` (ordered collection) support watchers that
fire on mutation and bubble up to parent nodes. All UI reactivity flows from
this — mutate the tree, watchers fire, UI updates.

### Mutation flow

All paths follow: **load → mutate → save**

- `loader.load_board()` reads the git branch into a Node tree (pass
  `committers=False` for one-shot CLI use)
- Mutation helpers in `model/card.py` and `model/column.py` operate on the tree
- `writer.save_board()` writes back using git plumbing — never touches the
  working tree. Blobs are written in-process via gitdb; the branch ref only
  advances by compare-and-swap, so concurrent writers are merged, never
  clobbered. Callers without their own merge step use `save_and_merge()`.
- The TUI's background sync (`sync.py`) snapshots the board with
  `board.clone()` before handing it to a worker thread, and reloads the board
  after every merge.

## UI architecture

Built on Textual. Message-driven — widgets post messages, screens handle them.

`NodeWatcherMixin` manages watch lifecycle and provides `suppressing()` context
to prevent feedback loops during writes.

Drag-and-drop uses `DraggableMixin` (on dragged widgets) and `DropTarget` (on
containers). The screen delegates mouse events to the active draggable.

## Testing

```
make          # install venv, run coverage
```

This is slow (~90s, ~700 tests). Don't run the full suite repeatedly — save it
for just before a commit that touches shared code. Run specific test files when
working on a focused area:

```
.venv/bin/pytest tests/model/test_card.py -x
```

Tests are **functional pytest style** (no unittest classes, no mocks). Fixtures
in `tests/model/conftest.py` create real temporary git repos. If something is
hard to test without mocks, the code needs refactoring. When fixing a bug,
verify the regression test fails on the pre-fix code (`git stash` the fix and
re-run) before committing.

## Task management

We are dogfooding ganban to manage this project's tasks, and the agent drives
the board. Use the CLI:

```
ganban board                      # board summary
ganban card list                  # list all cards
ganban card get 001               # read a card
ganban card move 001 --column 2   # move card to Now
ganban card add "title" --body …  # file a new card
```

The workflow, per card:

1. Move the card from Backlog into Now (column 2) when you start it.
2. Do the work: fix + regression test + focused test runs.
3. Commit — one code commit per card, message explains the why.
4. Move the card to Done (column 3) and pick up the next one.

Findings (bug reports, review results) become cards too — one card per
finding, labelled `bug`/`cleanup`/`ui`/etc., with file:line references and a
failure scenario in the body. The user may drop new cards into Backlog at any
time; when asked to pick up work, take what's in Now first, then pull from
Backlog. Concurrent use is safe: the CLI and a running TUI can both write to
the board (saves merge rather than clobber).
