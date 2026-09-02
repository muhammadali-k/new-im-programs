#!/usr/bin/env bash
# Publish the rendered tracker + data + skill to the GitHub repo (refreshes the Pages site).
# Usage: publish.sh [OUTPUT_DIR] [REPO_DIR]
# Defaults:
#   OUTPUT_DIR = ~/Library/CloudStorage/Dropbox/IM-Residency-New-Programs
#   REPO_DIR   = ~/Projects/new-im-programs   (a clone of muhammadali-k/new-im-programs)
set -euo pipefail

OUT="${1:-$HOME/Library/CloudStorage/Dropbox/IM-Residency-New-Programs}"
REPO="${2:-$HOME/Projects/new-im-programs}"
SKILL="$HOME/.claude/skills/new-im-programs"

if [ ! -d "$REPO/.git" ]; then
  echo "ERROR: git repo not found at $REPO" >&2
  echo "Clone it first:  gh repo clone muhammadali-k/new-im-programs \"$REPO\"" >&2
  exit 1
fi

# Sync tracker (as index.html for Pages), data, and the skill source.
cp "$OUT/new-im-programs.html" "$REPO/index.html"
cp "$OUT/programs.json"        "$REPO/programs.json"
cp "$OUT/new-im-programs.html" "$REPO/new-im-programs.html"
[ -d "$OUT/runs" ] && rsync -a --exclude '*.pdf' "$OUT/runs/" "$REPO/runs/"
rsync -a --delete --exclude '__pycache__' "$SKILL/" "$REPO/skill/"

cd "$REPO"
git add -A
if git diff --cached --quiet; then
  echo "No changes to publish."
  exit 0
fi
git commit -m "Update IM program tracker: $(date +%F)"
git push
echo "Published. Live: https://muhammadali-k.github.io/new-im-programs/"
