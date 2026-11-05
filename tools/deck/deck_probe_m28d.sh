#!/bin/bash
# deck_probe_m28d.sh - READ-ONLY, runs ON the Deck ('bash -s'). Both "strafe does not work" reports (17:0xZ and 20:17Z) came
# during Moonlight streaming sessions (sunshine.log CLIENT CONNECTED 17:04:04 and 20:16:59). So the input path is
# Flip 8 -> Sunshine -> virtual devices, not the Deck's own pad. Find out which virtual devices Sunshine created and what
# Steam did with them. Changes nothing.
set -u
echo "deck time $(date -u +%H:%MZ)"
echo "--- kernel: input devices registered since 16:50Z (Sunshine virtual gamepads/keyboards show up here)"
journalctl -k --since "16:50" -o short-iso 2>/dev/null | grep -i -E "input: |input[0-9]+" | cut -c1-170 | tail -20
echo "--- sunshine.log 17:03-17:13 and 20:15-now: everything that is not a video/audio stats line"
awk '/2026-11-03 17:0[3-9]|2026-11-03 17:1[0-3]|2026-11-03 20:(1[5-9]|[2-5][0-9])/' ~/.config/sunshine/sunshine.log 2>/dev/null \
  | grep -v -i -E "bitrate|fps|frame|encoder|packet|Hz|audio|video|rtsp|ping" | cut -c1-170 | tail -45
echo "--- sunshine.log: gamepad / controller / keyboard / libvirtualhid lines today"
grep -i -E "gamepad|controller|keyboard|virtualhid|uinput|evdev|rumble|motion" ~/.config/sunshine/sunshine.log 2>/dev/null | grep "2026-11-03" | cut -c1-170 | tail -25
echo "--- Steam controller log: connections today (which controllers Steam saw, incl. virtual ones)"
for f in ~/.steam/steam/logs/controller_ui.log ~/.steam/steam/logs/console-linux.txt; do
  [ -f "$f" ] && { echo "== $f"; grep -h -E "^\[2026-11-03 (17:0|17:1|20:1|20:2|20:3)" "$f" | grep -i -E "controller|gamepad|xbox|x-box|device|input|opened|closed|connected|disconnected|driver" | cut -c1-200 | tail -30; }
done
echo "--- Steam running? which mode of input handling (desktop)?"
pgrep -x steam >/dev/null && echo "steam running pid $(pgrep -x steam | head -1)" || echo "steam NOT running"
echo "--- current js/event nodes with ids (did a Sunshine gamepad appear and disappear?)"
for d in /sys/class/input/event*; do n=$(cat $d/device/name 2>/dev/null); id="$(cat $d/device/id/vendor 2>/dev/null):$(cat $d/device/id/product 2>/dev/null)"; echo "$(basename $d) $id $n"; done | grep -v -E "HD-Audio|Power Button|Lid|Video Bus|PC Speaker|Headset" 
echo "--- can alex read input devices without sudo? (group membership)"
id -nG
ls -l /dev/input/event7 /dev/input/event8 2>&1
echo "--- Moonlight client identity (paired clients)"
python3 - <<'EOF' 2>/dev/null || echo "no sunshine_state parse"
import json,glob
for f in glob.glob("/home/alex/.config/sunshine/sunshine_state.json"):
    j=json.load(open(f))
    for d in j.get("root",{}).get("named_devices",[]) or j.get("root",{}).get("devices",[]):
        print("paired:", d.get("name"), d.get("uuid","")[:8])
EOF
date -u +%H:%MZ
