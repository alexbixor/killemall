#!/bin/bash
# deck_m25_install.sh - runs ON the Deck (bash -s): M2.5 step B tape (textured ceiling + tint); same filename killemall48_m25.tap replaces the 22:0xZ one; launcher unchanged (picks newest tape).
# Headless self-test only - no window on the Deck screen.
set -u
cp /tmp/killemall48_m25.tap ~/Emulation/roms/zxspectrum/killemall48_m25.tap
echo "tape: $(stat -c '%s B' ~/Emulation/roms/zxspectrum/killemall48_m25.tap) sha256 $(sha256sum ~/Emulation/roms/zxspectrum/killemall48_m25.tap | cut -c1-16)"
ls -t ~/Emulation/roms/zxspectrum/killemall48_*.tap | head -1 | sed 's/^/launcher will pick (newest): /'
echo "--- headless self-test (no window, 8 s)"
KEA_HEADLESS=1 timeout 30 ~/.local/bin/launch-killemall; echo "self-test rc=$?"
tail -2 ~/.local/state/deck/killemall.log | cut -c1-160
pgrep -fa zesarux | grep -v pgrep | head -2 || echo "no zesarux left running"
date -u +%H:%MZ
