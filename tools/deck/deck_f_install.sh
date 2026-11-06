#!/bin/bash
# deck_f_install.sh - runs ON the Deck (bash -s): lane F = 128K shadow-screen flip (tear-free display, FLIP=1 build).
# 128K ONLY: the 48K tape is byte-identical to the live one, so it is not touched. Same filename killemall128_m25.tap
# (the launcher picks the newest killemall128_*.tap). The live M2.9 128K tape is kept as killemall128_m29.tap for rollback.
# Expects /tmp/killemall128_m25.tap (scp'd first). Headless self-test only - no window on the Deck.
set -u
ROMS=~/Emulation/roms/zxspectrum
exp128=b1681a3ba7842a03           # sha256 (first 16 hex) of the gated FLIP build, 08:07Z 6 Nov 2026
pgrep -x zesarux >/dev/null && { echo "ABORT: a game (zesarux) is running"; exit 3; }
if pgrep -f "reaper SteamLaunch" >/dev/null; then echo "ABORT: Steam game running"; exit 3; fi
h128=$(sha256sum /tmp/killemall128_m25.tap | cut -c1-16)
[ "$h128" = "$exp128" ] || { echo "ABORT: 128K tape hash $h128 != $exp128"; exit 3; }
echo "before: 128K live $(sha256sum $ROMS/killemall128_m25.tap | cut -c1-16) ($(stat -c '%y' $ROMS/killemall128_m25.tap | cut -c1-16))"
[ -f $ROMS/killemall128_m29.tap ] || cp -p $ROMS/killemall128_m25.tap $ROMS/killemall128_m29.tap
cp /tmp/killemall128_m25.tap $ROMS/killemall128_m25.tap
touch $ROMS/killemall128_m25.tap
for t in killemall128_m25 killemall128_m29 killemall128_m28 killemall48_m25; do
  [ -f $ROMS/$t.tap ] && echo "tape $t: $(stat -c '%s B' $ROMS/$t.tap) sha256 $(sha256sum $ROMS/$t.tap | cut -c1-16)"
done
echo "128K launcher will pick (newest): $(ls -t $ROMS/killemall128_*.tap | head -1)"
echo "48K launcher will pick (newest): $(ls -t $ROMS/killemall48_*.tap | head -1)"
echo "--- headless self-test 128K (no window, 8 s)"
KEA_HEADLESS=1 timeout 30 ~/.local/bin/launch-killemall128; echo "self-test 128K rc=$?"
pgrep -fa zesarux | grep -v pgrep | head -2 || echo "no zesarux left running"
rm -f /tmp/killemall128_m25.tap
date -u +%H:%M:%SZ
