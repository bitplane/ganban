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
│   ├── node.py          # Node (dict-like) and ListNode (ordered, id-keyed)
│   ├── loader.py        # Load board from git branch into Node tree
│   ├── writer.py        # Save Node tree back to git (plumbing, no checkout)
│   ├── card.py          # Card mutations: create, move, archive
│   └── column.py        # Column mutations: create, move, rename, archive
├── cli/                 # Argparse CLI
│   ├── __init__.py      # Parser & dispatch (noun-verb pattern)
│   ├── _common.py       # Shared helpers: load, save, output
│   ├── board.py         # board summary/get/set
│   ├── card.py          # card list/get/set/add/move/archive
│   ├── column.py        # column list/get/set/add/move/rename/archive
│   └── init.py          # ganban init
├── ui/                  # Textual TUI
│   ├── app.py           # GanbanApp, screen routing
│   ├── board.py         # BoardScreen (main screen)
│   ├── column.py        # ColumnWidget
│   ├── card.py          # CardWidget
│   ├── watcher.py       # NodeWatcherMixin (reactive watch + suppression)
│   ├── drag.py          # DraggableMixin + DropTarget
│   ├── detail.py        # Modal detail screens
│   ├── menu.py          # Context menus
│   └── edit/            # Editable widgets, section editors
├── git.py               # Async git wrappers (GitPython + asyncio.to_thread)
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

- `loader.load_board()` reads the git branch into a Node tree
- Mutation helpers in `model/card.py` and `model/column.py` operate on the tree
- `writer.save_board()` writes back using git plumbing (hash-object, mktree,
  commit-tree) — never touches the working tree

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

This is slow (~80s, 480+ tests). Don't run the full suite repeatedly — let the
user do it. Run specific test files when working on a focused area:

```
.venv/bin/pytest tests/model/test_card.py -x
```

Tests are **functional pytest style** (no unittest classes, no mocks). Fixtures
in `tests/model/conftest.py` create real temporary git repos. If something is
hard to test without mocks, the code needs refactoring.

## Task management

We are dogfooding ganban to manage this project's tasks. Use the CLI:

```
ganban board                      # board summary
ganban card list                  # list all cards
ganban card get 001               # read a card
ganban card move 001 --column 3   # move card to column 3
```

When asked to work on the next thing, the user will have put a card in the Doing
column. So pick it up for discussion and/or planning, we work on the feature
and the user will manage the card status. Once we have auto-update and merging
working then you can move the cards around using the CLI too.
