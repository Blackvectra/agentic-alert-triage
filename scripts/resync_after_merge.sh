#!/usr/bin/env bash
# Restart the working branch from main after its PR was squash-merged,
# keeping any local commits that were not in the merged PR. No force-push needed.
# Usage: scripts/resync_after_merge.sh [branch]   (default: current branch)
set -euo pipefail
branch="${1:-$(git rev-parse --abbrev-ref HEAD)}"
git diff --quiet && git diff --cached --quiet || { echo "commit or stash changes first"; exit 1; }

git fetch -q origin main "$branch"
remote_tip="origin/$branch"
# Local commits the remote branch doesn't have yet (not part of the merged PR).
unpushed=$(git rev-list --reverse "$remote_tip..HEAD")

git checkout -q -B "$branch" origin/main
# Record the old remote tip as merged, so the next push is a fast-forward.
git merge -q --no-edit -s ours "$remote_tip" -m "Resync branch after squash merge"
for c in $unpushed; do git cherry-pick "$c" >/dev/null; done

echo "Resynced $branch onto origin/main; re-applied $(echo $unpushed | wc -w) local commit(s)."
git log --oneline -5
