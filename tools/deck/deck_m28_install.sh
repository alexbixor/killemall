#!/bin/bash
# deck_m28_install.sh - runs ON the Deck (bash -s): M2.8 strafe fix (Z / X keys, pad L1/R1 and left-stick X did nothing
# before: the game loop never read the two strafe bits). 48K + 128K, same filenames killemall48_m25.tap / killemall128_m25.tap
# (launchers pick the newest killemall*_*.tap). The M2.6 tapes installed 16:17Z today are kept as *_m26.tap for rollback.
# Expects /tmp/killemall48_m25.tap and /tmp/killemall128_m25.tap (scp'd first). Headless self-tests only - no window on the Deck.
set -u
ROMS=~/Emulation/roms/zxspectrum
exp48=a969b1afff57dd8e; exp128=409b0cb77c04766f           # sha256 (first 16 hex) of the gated build, 17:3xZ 3 Nov 2026
h48=$(sha256sum /tmp/killemall48_m25.tap | cut -c1-16); h128=$(sha256sum /tmp/killemall128_m25.tap | cut -c1-16)
[ "$h48" = "$exp48" ] || { echo "ABORT: 48K tape hash $h48 != $exp48"; exit 3; }
[ "$h128" = "$exp128" ] || { echo "ABORT: 128K tape hash $h128 != $exp128"; exit 3; }
[ -f $ROMS/killemall48_m26.tap ] || cp -p $ROMS/killemall48_m25.tap $ROMS/killemall48_m26.tap
[ -f $ROMS/killemall128_m26.tap ] || cp -p $ROMS/killemall128_m25.tap $ROMS/killemall128_m26.tap
cp /tmp/killemall48_m25.tap $ROMS/killemall48_m25.tap
cp /tmp/killemall128_m25.tap $ROMS/killemall128_m25.tap
touch $ROMS/killemall48_m25.tap $ROMS/killemall128_m25.tap
for t in killemall48_m25 killemall128_m25 killemall48_m26 killemall128_m26 killemall48_e1 killemall128_e1; do
  [ -f $ROMS/$t.tap ] && echo "tape $t: $(stat -c '%s B' $ROMS/$t.tap) sha256 $(sha256sum $ROMS/$t.tap | cut -c1-16)"
done
echo "48K launcher will pick (newest): $(ls -t $ROMS/killemall48_*.tap | head -1)"
echo "128K launcher will pick (newest): $(ls -t $ROMS/killemall128_*.tap | head -1)"
echo "--- headless self-test 48K (no window, 8 s)"
KEA_HEADLESS=1 timeout 30 ~/.local/bin/launch-killemall; echo "self-test 48K rc=$?"
echo "--- headless self-test 128K (no window, 8 s)"
KEA_HEADLESS=1 timeout 30 ~/.local/bin/launch-killemall128; echo "self-test 128K rc=$?"
pgrep -fa zesarux | grep -v pgrep | head -2 || echo "no zesarux left running"
date -u +%H:%MZ
