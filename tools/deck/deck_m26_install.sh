#!/bin/bash
# deck_m26_install.sh - runs ON the Deck (bash -s): M2.6 tapes (per-cell colour P2E, ceiling D5, coloured items, blood flash +
# muzzle flash, floor stain) for 48K + 128K. Same filenames killemall48_m25.tap / killemall128_m25.tap replace the E1 (1 Nov)
# tapes, so the launchers (newest killemall*_*.tap) pick them up unchanged. E1 tapes kept as *_e1.tap for rollback.
# Expects /tmp/killemall48_m25.tap and /tmp/killemall128_m25.tap (scp'd first). Headless self-tests only - no window on the Deck.
set -u
ROMS=~/Emulation/roms/zxspectrum
# expected hashes (sha256, first 16 hex) of the files scp'd from hal-ec2 - refuse to install anything else
exp48=f6ebd4e6ad229b9c; exp128=d508e72912a60ddc
h48=$(sha256sum /tmp/killemall48_m25.tap | cut -c1-16); h128=$(sha256sum /tmp/killemall128_m25.tap | cut -c1-16)
[ "$h48" = "$exp48" ] || { echo "ABORT: 48K tape hash $h48 != $exp48"; exit 3; }
[ "$h128" = "$exp128" ] || { echo "ABORT: 128K tape hash $h128 != $exp128"; exit 3; }
# rollback copies of the E1 tapes (older mtime so the launchers never pick them over the new ones)
[ -f $ROMS/killemall48_e1.tap ] || cp -p $ROMS/killemall48_m25.tap $ROMS/killemall48_e1.tap
[ -f $ROMS/killemall128_e1.tap ] || cp -p $ROMS/killemall128_m25.tap $ROMS/killemall128_e1.tap
cp /tmp/killemall48_m25.tap $ROMS/killemall48_m25.tap
cp /tmp/killemall128_m25.tap $ROMS/killemall128_m25.tap
touch $ROMS/killemall48_m25.tap $ROMS/killemall128_m25.tap
for t in killemall48_m25 killemall128_m25 killemall48_e1 killemall128_e1; do
  echo "tape $t: $(stat -c '%s B' $ROMS/$t.tap) sha256 $(sha256sum $ROMS/$t.tap | cut -c1-16)"
done
echo "48K launcher will pick (newest): $(ls -t $ROMS/killemall48_*.tap | head -1)"
echo "128K launcher will pick (newest): $(ls -t $ROMS/killemall128_*.tap | head -1)"
echo "--- headless self-test 48K (no window, 8 s)"
KEA_HEADLESS=1 timeout 30 ~/.local/bin/launch-killemall; echo "self-test 48K rc=$?"
tail -2 ~/.local/state/deck/killemall.log | cut -c1-160
echo "--- headless self-test 128K (no window, 8 s)"
KEA_HEADLESS=1 timeout 30 ~/.local/bin/launch-killemall128; echo "self-test 128K rc=$?"
tail -2 ~/.local/state/deck/killemall128.log | cut -c1-160
pgrep -fa zesarux | grep -v pgrep | head -2 || echo "no zesarux left running"
ls ~/Desktop/Kill_em_all*.desktop
date -u +%H:%MZ
