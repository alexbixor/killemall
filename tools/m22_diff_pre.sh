#!/bin/bash
# m22_diff_pre.sh - what changed in the sources since the pre-M2.2 backup (read-only compare)
set -e
cd ~/work/killemall
rm -rf /tmp/pre22 && mkdir -p /tmp/pre22
tar xzf build/pre_m22/src_pre_m22.tgz -C /tmp/pre22
echo "backup tree:"; find /tmp/pre22 -maxdepth 2 -type d | head
for f in src/48k/kea48.asm src/common/frontend.asm src/common/state.asm tools/gen48.py tools/test_frontend.py tools/fe_test_main.asm; do
  old=$(find /tmp/pre22 -path "*${f}" | head -1)
  if [ -z "$old" ]; then echo "== $f: not in backup"; continue; fi
  n=$(diff "$old" "$f" | grep -c '^[<>]' || true)
  echo "== $f: $n changed lines"
done
echo "---- frontend.asm diff:"; diff "$(find /tmp/pre22 -path '*src/common/frontend.asm' | head -1)" src/common/frontend.asm || true
echo "---- kea48.asm diff (first 80 lines):"; diff "$(find /tmp/pre22 -path '*src/48k/kea48.asm' | head -1)" src/48k/kea48.asm | head -80 || true
echo "---- gen48.py diff:"; diff "$(find /tmp/pre22 -path '*tools/gen48.py' | head -1)" tools/gen48.py || true
echo "---- hi_end before:"; grep -E "^hi_end" build/pre_m22/kea48_pre_m22.sym 2>/dev/null || ls build/pre_m22/
