#!/bin/bash
# deck_m2_install.sh - runs ON the Deck (bash -s): lane M2 = 128K real sprites for enemy types 3..6 (shotgunner, floater, brute,
# boss) through the bank-3 hi-res blitter on the DEFAULT tape (7 Nov 2026). Until now the four types drawn with zombie frames.
# 128K ONLY (default tape + the hi-res experimental icon's tape): the 48K tape is byte-identical to the live one, not touched.
# Same filename killemall128_m25.tap (the launcher picks the newest killemall128_*.tap). The F2 tape that is live now is kept as
# killemall128_f2.tap for rollback (rollback = `touch ~/Emulation/roms/zxspectrum/killemall128_f2.tap`, newest wins);
# K1 (killemall128_k1.tap) and lane-F (killemall128_f.tap) tapes stay. Expects /tmp/killemall128_m25.tap and
# /tmp/killemall128_hires_experimental.tap (scp'd first). Headless self-test only - no window on the Deck.
set -u
ROMS=~/Emulation/roms/zxspectrum
exp128=d439fd188746302e           # sha256 (first 16 hex) of the gated M2 default build, 66194 B (build/night/M2_identity.out)
exphr=637a2610fb61f810            # sha256 of the M2 hi-res experimental tape, 66194 B
expold=b23dd27ba1f26169           # sha256 of the F2 tape that should be live now (57602 B)
pgrep -x zesarux >/dev/null && { echo "ABORT: a game (zesarux) is running"; exit 3; }
if pgrep -f "reaper SteamLaunch" >/dev/null; then echo "ABORT: Steam game running"; exit 3; fi
h128=$(sha256sum /tmp/killemall128_m25.tap | cut -c1-16)
[ "$h128" = "$exp128" ] || { echo "ABORT: 128K tape hash $h128 != $exp128"; exit 3; }
hhr=$(sha256sum /tmp/killemall128_hires_experimental.tap | cut -c1-16)
[ "$hhr" = "$exphr" ] || { echo "ABORT: hi-res tape hash $hhr != $exphr"; exit 3; }
live=$(sha256sum $ROMS/killemall128_m25.tap | cut -c1-16)
echo "before: 128K live $live ($(stat -c '%y' $ROMS/killemall128_m25.tap | cut -c1-16))"
[ "$live" = "$expold" ] || { echo "NOTE: live tape is not the F2 build ($expold) - keeping it as killemall128_prev_$live.tap too"; cp -p $ROMS/killemall128_m25.tap $ROMS/killemall128_prev_$live.tap; }
[ -f $ROMS/killemall128_f2.tap ] || cp -p $ROMS/killemall128_m25.tap $ROMS/killemall128_f2.tap
cp /tmp/killemall128_m25.tap $ROMS/killemall128_m25.tap
touch $ROMS/killemall128_m25.tap
hr=$ROMS/experimental/killemall128_hires_experimental.tap     # the hi-res icon's explicit tape path (deck_n3f_hires_install.sh)
if [ -f "$hr" ]; then
  echo "hi-res experimental before: $(basename "$hr") sha256 $(sha256sum "$hr" | cut -c1-16) -> kept as $(basename "${hr%.tap}_f2.tap")"
  [ -f "${hr%.tap}_f2.tap" ] || cp -p "$hr" "${hr%.tap}_f2.tap"
  cp /tmp/killemall128_hires_experimental.tap "$hr"; touch "$hr"
else
  echo "NOTE: no hi-res experimental tape at $hr - skipped"
fi
for t in killemall128_m25 killemall128_f2 killemall128_k1 killemall128_f killemall128_m29 killemall48_m25; do
  [ -f $ROMS/$t.tap ] && echo "tape $t: $(stat -c '%s B' $ROMS/$t.tap) sha256 $(sha256sum $ROMS/$t.tap | cut -c1-16)"
done
echo "128K launcher will pick (newest): $(basename "$(ls -t $ROMS/killemall128_*.tap | head -1)")"
echo "48K launcher will pick (newest): $(basename "$(ls -t $ROMS/killemall48_*.tap | head -1)")"
echo "hi-res experimental folder: $(cd $ROMS/experimental 2>/dev/null && for f in *.tap; do echo -n "$f=$(sha256sum $f | cut -c1-16) "; done)"
echo "--- headless self-test 128K (no window, 8 s)"
KEA_HEADLESS=1 timeout 30 ~/.local/bin/launch-killemall128; echo "self-test 128K rc=$?"
pgrep -fa zesarux | grep -v pgrep | head -2 || echo "no zesarux left running"
rm -f /tmp/killemall128_m25.tap /tmp/killemall128_hires_experimental.tap
date -u +%H:%M:%SZ
