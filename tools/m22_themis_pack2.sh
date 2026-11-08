#!/bin/bash
# m22_themis_pack2.sh - r2b packet: the SOURCE tree only (no .venv, no build/ images), tests runnable from the packet copy.
set -e
cd ~/work/killemall
W=$HOME/.hermes/profiles/themis/work/killemall-m22-20261028
rm -rf "$W/tree" "$W/evidence-claimed"
mkdir -p "$W/tree" "$W/evidence-claimed"
# source + tools + assets (what the tests need), nothing else
rsync -a --exclude '.venv' --exclude 'build' --exclude '__pycache__' --exclude '*.pyc' --exclude 'zesarux' --exclude 'z88dk' --exclude 'z88dk-src-2.4.tgz' --exclude 'zesarux.tgz' --exclude '*.log' src tools assets "$W/tree/"
mkdir -p "$W/tree/tools/zesarux"
mkdir -p "$W/tree/build"
cp build/killemall48_m22.tap build/kea48.sym build/kea48.tap build/killemall48_m2_orig.tap "$W/tree/build/" 2>/dev/null || true
cp tools/zesarux/48.rom "$W/tree/tools/zesarux/" 2>/dev/null || true
# claimed evidence: gate outputs + measurements, named as claims
cp build/m22_gates_step4.out "$W/evidence-claimed/t6_gates_step4.out"
cp build/t6_test_game_hud.out "$W/evidence-claimed/test_game_hud.out" 2>/dev/null || true
cp build/m22_build_last.log "$W/evidence-claimed/build_last.log"
cp build/m22_sheet.png build/m22_pair_v1.png "$W/evidence-claimed/"
timeout 300 .venv/bin/python tools/test_game_hud.py > "$W/evidence-claimed/test_game_hud_r2b.out" 2>&1 || true
timeout 300 .venv/bin/python tools/m22_stack.py > "$W/evidence-claimed/stack_depth.out" 2>&1 || true
# fresh diff vs pre-M2.2 (includes the D1/D2 fixes)
bash tools/m22_diff_all.sh > /dev/null 2>&1 || true
( cd /tmp/pre22 && diff -ruN src ~/work/killemall/src ; diff -ruN tools/gen48.py ~/work/killemall/tools/gen48.py ) > "$W/DIFF-pre_m22-to-m22-r2b.patch" 2>/dev/null || true
cd "$W" && find tree evidence-claimed DIFF-pre_m22-to-m22-r2b.patch -type f -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS-r2b
du -sh "$W/tree" "$W/evidence-claimed"
wc -l "$W/SHA256SUMS-r2b" "$W/DIFF-pre_m22-to-m22-r2b.patch"
# prove the suites run from the PACKET copy with the project's interpreter (so Themis does not need .venv in the tree)
cd "$W/tree" && timeout 120 ~/work/killemall/.venv/bin/python tools/test_game_hud.py 2>&1 | tail -1
