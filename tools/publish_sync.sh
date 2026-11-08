#!/bin/bash
# publish_sync.sh - push the private repo's new commits into the public mirror (github.com/alexbixor/killemall).
# Flow: re-run the filter (tools/publish_prepare.sh) into a scratch clone, then rebase the public-only commits
# (LICENSE/README/CI/location-independent build scripts, kept on the mirror's main) on top of the filtered history.
# Idempotent; aborts if the secret scan finds anything.  Never pushes with --force unless FORCE=1.
set -e
SRC=/home/ubuntu/work/killemall
PUB=/home/ubuntu/work/killemall_pub
bash "$SRC/tools/publish_prepare.sh" > "$SRC/build/night/PUB_prepare.out" 2>&1 || { tail -5 "$SRC/build/night/PUB_prepare.out"; exit 1; }
cd "$PUB"
grep -q "^0$" "$SRC/build/night/PUB_prepare.out" || { echo "secret scan not clean - see build/night/PUB_prepare.out"; exit 1; }
# publish_prepare.sh recreated $PUB from scratch, so the mirror's extra commits live only on GitHub: fetch and rebase them.
git remote add origin https://github.com/alexbixor/killemall.git
git fetch -q origin main
FILTERED_HEAD=$(git rev-parse HEAD)
git checkout -q -B main origin/main
# the public-only commits are those on origin/main whose subjects are not in the filtered history
git rebase -q --onto "$FILTERED_HEAD" "$(git merge-base origin/main "$FILTERED_HEAD" 2>/dev/null || git rev-list --max-parents=0 origin/main)" main 2>/dev/null || {
  echo "rebase conflict - resolve by hand in $PUB"; exit 1; }
git log --oneline -3 | cut -c1-100
if [ "${FORCE:-0}" = 1 ]; then git push --force-with-lease origin main; else git push origin main; fi
