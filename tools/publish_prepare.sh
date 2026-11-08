#!/bin/bash
# publish_prepare.sh - build the curated public mirror of Kill'em all in $PUB from the private working repo.
# Keeps src/ tools/ assets/ docs/ *.md with full commit history; drops build/ ref/ and *.log; scrubs the Deck address.
# Usage: tools/publish_prepare.sh            (writes /home/ubuntu/work/killemall_pub, never touches the source repo)
set -e
SRC=/home/ubuntu/work/killemall
PUB=/home/ubuntu/work/killemall_pub
FR="python3 $HOME/.local/bin/git-filter-repo"
rm -rf "$PUB"
git clone -q --no-local "$SRC" "$PUB"
cd "$PUB"
git remote remove origin
# pass 1: keep only the public paths
printf 'src\ntools\nassets\ndocs\nDESIGN.md\nARCH_M2.md\n.gitignore\n' > /tmp/pub_keep.txt
$FR --force --paths-from-file /tmp/pub_keep.txt
# pass 2: drop logs and scrub the Deck ssh target (host literal first, then user@host form)
printf 'regex:alex@100\\.123\\.94\\.62==>${DECK:?set DECK=user@host}\nregex:100\\.123\\.94\\.62==>DECK_HOST\n' > /tmp/pub_replace.txt
$FR --force --invert-paths --path-glob 'tools/*.log' --path-glob 'tools/zes_src_probe*.py'
$FR --force --replace-text /tmp/pub_replace.txt
git gc -q --prune=now
echo "pub repo: $(git rev-list --count HEAD) commits, $(git ls-files | wc -l) files, $(du -sh .git | cut -f1) .git"
echo "secret scan (expect 0):"; git grep -c -E "100\.123\.94|alex@" -- . | wc -l
git log --all --format=%B | grep -c -E "100\.123\.94|alex@" || true
