#!/bin/bash
# deck_probe_m28h.sh - READ-ONLY pre-flight for the live Z/X experiment (runs ON the Deck via 'bash -s').
set -u
echo "deck $(date -u +%H:%M:%SZ)"
ls -l /dev/uinput; getfacl -p /dev/uinput 2>/dev/null | grep user
python3 -c "import evdev; print('evdev ok', evdev.__file__)" 2>&1 | tail -1
for t in xdotool ydotool wtype xev; do command -v $t || echo "no $t"; done
ls /tmp/.X11-unix/
pgrep -fa zesarux | grep -v pgrep | head -1 || echo "no zesarux"
~/.local/bin/sunshine-stream-hook status 2>/dev/null | head -5
grep -E "CLIENT (CONN|DISC)" ~/.config/sunshine/sunshine.log | tail -1
pgrep -fa "reaper SteamLaunch" | grep -v pgrep | head -1 || echo "no steam game"
md5sum ~/.local/bin/launch-killemall128 ~/.local/bin/launch-killemall
ls ~/Applications/zesarux/zesarux && ~/Applications/zesarux/zesarux --version 2>/dev/null | head -1
