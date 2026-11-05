#!/bin/bash
# deck_m23_install.sh - runs ON the Deck (bash -s): M2.3 tape + updated launcher (A = SPACE = fire, X = M = open), headless self-test
set -u
install -m 755 /tmp/launch-killemall.sh ~/.local/bin/launch-killemall
cp /tmp/killemall48_m23.tap ~/Emulation/roms/zxspectrum/killemall48_m23.tap
echo "tape: $(stat -c '%s B' ~/Emulation/roms/zxspectrum/killemall48_m23.tap) sha256 $(sha256sum ~/Emulation/roms/zxspectrum/killemall48_m23.tap | cut -c1-16)"
ls -t ~/Emulation/roms/zxspectrum/killemall48_*.tap | head -1 | sed 's/^/launcher will pick (newest): /'
grep -c 'joystickkeybt 0 32' ~/.local/bin/launch-killemall | sed 's/^/launcher has A->SPACE: /'
echo "--- headless self-test (no window, 8 s)"
KEA_HEADLESS=1 timeout 30 ~/.local/bin/launch-killemall; echo "self-test rc=$?"
tail -2 ~/.local/state/deck/killemall.log | cut -c1-160
grep -ciE 'error|cannot|unknown' ~/.local/state/deck/killemall.log | sed 's/^/log error lines: /'
pgrep -fa zesarux | grep -v pgrep | head -2 || echo "no zesarux left running"
date -u +%H:%MZ