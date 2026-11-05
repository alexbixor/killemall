#!/bin/bash
# deck_m25c_install.sh - runs ON the Deck (bash -s): M2.5 step C tapes (192-px window), 48K + 128K; same filenames
# killemall48_m25.tap / killemall128_m25.tap replace the step B ones (launchers pick the newest tape; m22/m23/m24 fallbacks stay).
# Headless self-tests only - no window on the Deck screen.
set -u
cp /tmp/killemall48_m25.tap ~/Emulation/roms/zxspectrum/killemall48_m25.tap
cp /tmp/killemall128_m25.tap ~/Emulation/roms/zxspectrum/killemall128_m25.tap
for t in killemall48_m25 killemall128_m25; do
  echo "tape $t: $(stat -c '%s B' ~/Emulation/roms/zxspectrum/$t.tap) sha256 $(sha256sum ~/Emulation/roms/zxspectrum/$t.tap | cut -c1-16)"
done
ls -t ~/Emulation/roms/zxspectrum/killemall48_*.tap | head -1 | sed 's/^/48K launcher will pick (newest): /'
ls -t ~/Emulation/roms/zxspectrum/killemall128_*.tap | head -1 | sed 's/^/128K launcher will pick (newest): /'
echo "--- headless self-test 48K (no window, 8 s)"
KEA_HEADLESS=1 timeout 30 ~/.local/bin/launch-killemall; echo "self-test 48K rc=$?"
tail -2 ~/.local/state/deck/killemall.log | cut -c1-160
echo "--- headless self-test 128K (no window, 8 s)"
KEA_HEADLESS=1 timeout 30 ~/.local/bin/launch-killemall128; echo "self-test 128K rc=$?"
tail -2 ~/.local/state/deck/killemall128.log | cut -c1-160
pgrep -fa zesarux | grep -v pgrep | head -2 || echo "no zesarux left running"
ls ~/Desktop/Kill_em_all*.desktop
date -u +%H:%MZ
