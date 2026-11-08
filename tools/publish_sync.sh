#!/bin/bash
# publish_sync.sh - push the private repo's new commits into the public mirror (github.com/alexbixor/killemall).
# Flow: re-run the filter (tools/publish_prepare.sh) into a scratch clone, rebase the public-only commits
# (LICENSE/README/CI/location-independent build scripts, kept on the mirror's main) on top of the filtered history,
# refresh the CI sha256 pins from the private repo's gated build/ tapes, push.
# git-filter-repo re-hashes every commit, so the mirror's history is always "rewritten" relative to GitHub:
# the push MUST be --force-with-lease (a plain push is rejected non-fast-forward every time - learned 8 Nov 10:21Z).
# Idempotent; aborts if the secret scan finds anything. Standing rule (Alex, 8 Nov 10:38Z): run after EVERY private commit.
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
git rebase -q --onto "$FILTERED_HEAD" "$(git merge-base origin/main "$FILTERED_HEAD")" main || { echo "rebase conflict - resolve by hand in $PUB"; exit 1; }
# CI pins: the mirror's CI rebuilds and compares against tools/ci_expected_sha256.txt; refresh from the private gated tapes.
CHANGED=""
for f in build/kea48.tap build/kea128.tap build/killemall128_m2.tap build/next/killemall_b.nex; do
  [ -f "$SRC/$f" ] || continue
  H=$(sha256sum "$SRC/$f" | cut -c1-64)
  if ! grep -q "^$H  $f\$" tools/ci_expected_sha256.txt; then
    sed -i "s|^[0-9a-f]\{64\}  $f\$|$H  $f|" tools/ci_expected_sha256.txt
    CHANGED="$CHANGED ${f##*/}=${H:0:8}"
  fi
done
if [ -n "$CHANGED" ]; then
  git add tools/ci_expected_sha256.txt
  git commit -q -m "ci: refresh sha256 pins from the gated private build:$CHANGED"
  echo "ci pins updated:$CHANGED"
fi
git log --oneline -4 | cut -c1-100
git push --force-with-lease origin main 2>&1 | tail -1
