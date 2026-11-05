#!/bin/bash
# deck_probe_m28b.sh - READ-ONLY survey after Alex reported "strafe X Z still does not work" (3 Nov 2026, ~20:20Z).
# Runs ON the Deck via 'bash -s'. Changes nothing. Questions: which tape did his launches after the 17:41Z install
# actually load, with which joystick device, is the emulator running now, what do the Steam shortcuts launch.
set -u
echo "deck time $(date -u +%H:%MZ) uptime: $(uptime -p)"
ROMS=~/Emulation/roms/zxspectrum
echo "--- tapes (mtime, size, sha256 head)"
for t in "$ROMS"/killemall*.tap; do
  echo "$(basename "$t") $(stat -c '%y' "$t" | cut -c1-19) $(stat -c '%s' "$t") B sha256 $(sha256sum "$t" | cut -c1-16)"
done
echo "48K launcher picks (newest): $(ls -t "$ROMS"/killemall48_*.tap | head -1)"
echo "128K launcher picks (newest): $(ls -t "$ROMS"/killemall128_*.tap | head -1)"
echo "--- launcher logs: launch lines (tape= js= headless=) today"
grep -h "tape=" ~/.local/state/deck/killemall.log ~/.local/state/deck/killemall128.log 2>/dev/null | grep "$(date -u +%F)" | tail -12
echo "--- last 3 lines of each log (any zesarux complaints?)"
tail -3 ~/.local/state/deck/killemall.log 2>/dev/null | cut -c1-160
tail -3 ~/.local/state/deck/killemall128.log 2>/dev/null | cut -c1-160
echo "--- running now?"
pgrep -fa zesarux | grep -v pgrep | cut -c1-200 || echo "no zesarux running"
pgrep -fa "reaper SteamLaunch" | grep -v pgrep | cut -c1-160 | head -2 || echo "no Steam game running"
systemctl --user -q is-active gamescope-session.service && echo "mode: Game Mode" || echo "mode: Desktop"
echo "--- joystick devices seen now"
for j in /dev/input/js*; do echo "$j: $(cat /sys/class/input/${j##*/}/device/name 2>/dev/null)"; done
echo "--- Steam shortcuts mentioning killemall (launch options)"
for f in ~/.steam/steam/userdata/*/config/shortcuts.vdf ~/.local/share/Steam/userdata/*/config/shortcuts.vdf; do
  [ -f "$f" ] && { echo "$f"; strings "$f" | grep -i -A3 -B3 killemall | cut -c1-160 | head -30; }
done
echo "--- launcher scripts live on the Deck (hash + the exec line)"
for s in ~/.local/bin/launch-killemall ~/.local/bin/launch-killemall128; do
  [ -f "$s" ] && { echo "$s sha256 $(sha256sum "$s" | cut -c1-16) $(stat -c '%y' "$s" | cut -c1-19)"; grep -n -E "joystickkeybt|joystickemulated|TAP=" "$s" | cut -c1-200; }
done
echo "--- zesarux version on the Deck"
~/Applications/zesarux/zesarux --version 2>/dev/null | head -2 || echo "no --version"
echo "--- keyboard layout (X11, for the Z/X keysyms)"
export XDG_RUNTIME_DIR=/run/user/$(id -u); export DISPLAY=${DISPLAY:-:0}
setxkbmap -query 2>/dev/null | head -4 || echo "setxkbmap unavailable"
echo "--- input devices that look like keyboards"
grep -E "^N: Name=" /proc/bus/input/devices | grep -i -E "keyboard|keybo" | cut -c1-120
date -u +%H:%MZ
