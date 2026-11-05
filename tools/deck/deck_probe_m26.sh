#!/bin/bash
# deck_probe_m26.sh - READ-ONLY survey before the M2.6 push (runs ON the Deck via 'bash -s'): is Alex playing/streaming,
# which Kill'em all tapes are live, launcher state. Changes nothing.
set -u
echo "deck time $(date -u +%H:%MZ) uptime: $(uptime -p)"
echo "--- live tapes"
for t in ~/Emulation/roms/zxspectrum/killemall48_m25.tap ~/Emulation/roms/zxspectrum/killemall128_m25.tap; do
  [ -f "$t" ] && echo "$(basename "$t") $(stat -c '%s B %y' "$t" | cut -c1-30) sha256 $(sha256sum "$t" | cut -c1-16)" || echo "MISSING $t"
done
echo "48K launcher picks: $(ls -t ~/Emulation/roms/zxspectrum/killemall48_*.tap | head -1)"
echo "128K launcher picks: $(ls -t ~/Emulation/roms/zxspectrum/killemall128_*.tap | head -1)"
echo "--- is anything running that a headless self-test could disturb?"
pgrep -fa "reaper SteamLaunch" | grep -v pgrep | head -2 || echo "no Steam game running"
pgrep -fa zesarux | grep -v pgrep | head -2 || echo "no zesarux running"
~/.local/bin/sunshine-stream-hook status 2>/dev/null | head -4 || echo "sunshine-stream-hook status unavailable"
systemctl --user -q is-active gamescope-session.service && echo "mode: Game Mode" || echo "mode: Desktop"
echo "load: $(cut -d' ' -f1-3 /proc/loadavg)"
tail -1 ~/.local/state/deck/killemall.log 2>/dev/null | cut -c1-120
tail -1 ~/.local/state/deck/killemall128.log 2>/dev/null | cut -c1-120
