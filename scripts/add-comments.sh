#!/usr/bin/env bash
set -e

CARD="$1"

if [ -z "$CARD" ]; then
    echo "Usage: $0 <card-file-path>"
    exit 1
fi

WORKTREE=$(mktemp -d)
trap 'git worktree remove "$WORKTREE"' EXIT
git worktree add "$WORKTREE" ganban

echo "" >> "$WORKTREE/$CARD"
echo "## comments" >> "$WORKTREE/$CARD"
git -C "$WORKTREE" add "$CARD"
git -C "$WORKTREE" commit -n -m "Update board"

declare -a NAMES=("Alice Cooper" "Bob Marley" "Charlie Brown" "Diana Prince" "Eve Torres" "Frank Castle" "Grace Hopper" "Hank Scorpio")
declare -a EMAILS=("alice@example.com" "bob@reggae.org" "charlie@peanuts.com" "diana@themyscira.gov" "eve@crypto.net" "frank@punisher.mil" "grace@navy.mil" "hank@globex.com")

for i in "${!NAMES[@]}"; do
    NAME="${NAMES[$i]}"
    EMAIL="${EMAILS[$i]}"
    echo "" >> "$WORKTREE/$CARD"
    echo "* [$NAME](mailto:$EMAIL) - comment from $NAME" >> "$WORKTREE/$CARD"
    git -C "$WORKTREE" add "$CARD"
    git -C "$WORKTREE" commit -n --author="$NAME <$EMAIL>" -m "Update board"
done
