#!/bin/bash
# deck_zes_probe2.sh - READ-ONLY: joystick table syntax + which js devices exist + steam state
sed -n 305,330p /tmp/zes_help2.txt | cut -c1-200
echo "--- js devices"
grep -B5 -A1 -E 'Handlers=.*js[0-9]' /proc/bus/input/devices | grep -E 'Name|Handlers|Phys|Uniq'
for j in /dev/input/js*; do echo "$j: $(udevadm info -q property $j 2>/dev/null | grep -E '^(ID_INPUT_JOYSTICK|ID_VENDOR|ID_MODEL|ID_INPUT_JOYSTICK_INTEGRATION)=' | tr '\n' ' ')"; done
echo "--- steam"
pgrep -x steam >/dev/null && echo "steam running, unit=$(basename "$(cut -d: -f3 /proc/$(pgrep -x steam | head -1)/cgroup)")" || echo "steam not running"
pgrep -fa 'reaper SteamLaunch' | head -2 || true
echo "--- zesaruxrc tail"
grep -vE '^;|^$' ~/.zesaruxrc | head -40
date -u +%H:%MZ
