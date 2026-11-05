#!/bin/bash
# deck_m29_install.sh - runs ON the Deck (bash -s): M2.9 fixed time step (10 game steps/s from the 50 Hz ticks counter on
# 48K, 128K and Next). 48K + 128K, same filenames killemall48_m25.tap / killemall128_m25.tap (launchers pick the newest
# killemall*_*.tap). The M2.8 strafe tapes are kept as *_m28.tap for rollback (M2.6 ones stay as *_m26.tap).
# Expects /tmp/killemall48_m25.tap and /tmp/killemall128_m25.tap (scp'd first). Headless self-tests only - no window on the Deck.
set -u
ROMS=~/Emulation/roms/zxspectrum
exp48=d4eda0898c25232c; exp128=24b5a1ef49a5c981           # sha256 (first 16 hex) of the gated build, 10:30Z 4 Nov 2026
pgrep -x zesarux >/dev/null && { echo "ABORT: a game (zesarux) is running"; exit 3; }
if pgrep -f "reaper SteamLaunch" >/dev/null; then echo "ABORT: Steam game running"; exit 3; fi
h48=$(sha256sum /tmp/killemall48_m25.tap | cut -c1-16); h128=$(sha256sum /tmp/killemall128_m25.tap | cut -c1-16)
[ "$h48" = "$exp48" ] || { echo "ABORT: 48K tape hash $h48 != $exp48"; exit 3; }
[ "$h128" = "$exp128" ] || { echo "ABORT: 128K tape hash $h128 != $exp128"; exit 3; }
echo "before: 48K live $(sha256sum $ROMS/killemall48_m25.tap | cut -c1-16)  128K live $(sha256sum $ROMS/killemall128_m25.tap | cut -c1-16)"
[ -f $ROMS/killemall48_m28.tap ] || cp -p $ROMS/killemall48_m25.tap $ROMS/killemall48_m28.tap
[ -f $ROMS/killemall128_m28.tap ] || cp -p $ROMS/killemall128_m25.tap $ROMS/killemall128_m28.tap
cp /tmp/killemall48_m25.tap $ROMS/killemall48_m25.tap
cp /tmp/killemall128_m25.tap $ROMS/killemall128_m25.tap
touch $ROMS/killemall48_m25.tap $ROMS/killemall128_m25.tap
for t in killemall48_m25 killemall128_m25 killemall48_m28 killemall128_m28 killemall48_m26 killemall128_m26; do
  [ -f $ROMS/$t.tap ] && echo "tape $t: $(stat -c '%s B' $ROMS/$t.tap) sha256 $(sha256sum $ROMS/$t.tap | cut -c1-16)"
done
echo "48K launcher will pick (newest): $(ls -t $ROMS/killemall48_*.tap | head -1)"
echo "128K launcher will pick (newest): $(ls -t $ROMS/killemall128_*.tap | head -1)"
echo "--- headless self-test 48K (no window, 8 s)"
KEA_HEADLESS=1 timeout 30 ~/.local/bin/launch-killemall; echo "self-test 48K rc=$?"
echo "--- headless self-test 128K (no window, 8 s)"
KEA_HEADLESS=1 timeout 30 ~/.local/bin/launch-killemall128; echo "self-test 128K rc=$?"
pgrep -fa zesarux | grep -v pgrep | head -2 || echo "no zesarux left running"
date -u +%H:%M:%SZ
