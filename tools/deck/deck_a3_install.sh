#!/bin/bash
# deck_a3_install.sh - runs ON the Deck (bash -s): lane A3 merge = hand-drawn 32x48 art for enemy types 3..6 on the DEFAULT
# 128K tape + boss ink white (was bright blue). Same filenames as the M2 install (killemall128_m25.tap default icon,
# experimental/killemall128_hires_experimental.tap hi-res icon). The M2 tapes live now are kept for rollback
# (killemall128_m2_m2tap.tap / hires_m2.tap style side names). 48K tape byte-identical, not touched.
# Expects /tmp/killemall128_m25.tap (= build/killemall128_m2.tap aafcdfd8) and
# /tmp/killemall128_hires_experimental.tap (= build/killemall128_hires.tap 99473bd4), scp'd first. Headless self-test only.
set -u
ROMS=~/Emulation/roms/zxspectrum
exp128=aafcdfd8ca2ff900           # sha256 (first 16 hex) of the gated A3-merge default build, 66706 B (A3_merge_build.out)
exphr=99473bd40d070990            # sha256 of the A3-merge hi-res tape, 66706 B
expold=d439fd188746302e           # sha256 of the M2 tape that should be live now
pgrep -x zesarux >/dev/null && { echo "ABORT: a game (zesarux) is running"; exit 3; }
if pgrep -f "reaper SteamLaunch" >/dev/null; then echo "ABORT: Steam game running"; exit 3; fi
h128=$(sha256sum /tmp/killemall128_m25.tap | cut -c1-16)
[ "$h128" = "$exp128" ] || { echo "ABORT: 128K tape hash $h128 != $exp128"; exit 3; }
hhr=$(sha256sum /tmp/killemall128_hires_experimental.tap | cut -c1-16)
[ "$hhr" = "$exphr" ] || { echo "ABORT: hi-res tape hash $hhr != $exphr"; exit 3; }
live=$(sha256sum $ROMS/killemall128_m25.tap | cut -c1-16)
echo "before: 128K live $live"
if [ "$live" = "$expold" ]; then
  cp -p $ROMS/killemall128_m25.tap $ROMS/killemall128_m2_rollback.tap   # the M2 build, kept for rollback
else
  echo "NOTE: live tape $live is not the M2 build ($expold) - kept as killemall128_prev_$live.tap too"
  cp -p $ROMS/killemall128_m25.tap $ROMS/killemall128_prev_$live.tap
fi
cp /tmp/killemall128_m25.tap $ROMS/killemall128_m25.tap
touch $ROMS/killemall128_m25.tap
hr=$ROMS/experimental/killemall128_hires_experimental.tap
if [ -f "$hr" ]; then
  echo "hi-res before: $(sha256sum "$hr" | cut -c1-16)"
  [ -f "${hr%.tap}_m2.tap" ] || cp -p "$hr" "${hr%.tap}_m2.tap"
  cp /tmp/killemall128_hires_experimental.tap "$hr"; touch "$hr"
  echo "hi-res installed: $(sha256sum "$hr" | cut -c1-16)"
fi
echo "installed: 128K $(sha256sum $ROMS/killemall128_m25.tap | cut -c1-16) $(stat -c %s $ROMS/killemall128_m25.tap) B"
KEA_HEADLESS=1 timeout 20 launch-killemall128 >/dev/null 2>&1
echo "self-test rc=$? (124 = ran the full 8 s window fine)"
pkill -x zesarux 2>/dev/null; sleep 1
pgrep -x zesarux >/dev/null && echo "WARN: zesarux still running" || echo "emulator clean"
echo "after: $(sha256sum $ROMS/killemall128_m25.tap | cut -c1-16)"
