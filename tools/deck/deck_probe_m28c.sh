#!/bin/bash
# deck_probe_m28c.sh - READ-ONLY, runs ON the Deck ('bash -s'). Strafe still "not working" for Alex at 20:17-20:20Z 3 Nov 2026.
# The game code is proven (real tape in ZEsarUX on hal-ec2 slides on Z/X). What is NOT proven is the Deck's input path:
# how he launched (Steam shortcut vs desktop icon), what the pad really is (Steam virtual 28de:11ff vs Sunshine), the
# Steam Input per-game layout (L1/R1/left stick), whether he is streaming, and what ZEsarUX logged about the joystick.
set -u
echo "deck time $(date -u +%H:%MZ)"
echo "--- streaming now / recently?"
~/.local/bin/sunshine-stream-hook status 2>/dev/null | head -5 || echo "hook status unavailable"
grep -h -E "CLIENT CONNECTED|CLIENT DISCONNECTED" ~/.config/sunshine/sunshine.log 2>/dev/null | tail -3 | cut -c1-120
echo "--- js devices: vendor:product + name (28de:11ff = Steam virtual pad)"
for j in /sys/class/input/js*; do d=$j/device; echo "$(basename $j) $(cat $d/id/vendor 2>/dev/null):$(cat $d/id/product 2>/dev/null) $(cat $d/name 2>/dev/null) uniq=$(cat $d/uniq 2>/dev/null)"; done
echo "--- all input devices (name + handlers) for the full picture"
awk '/^N: Name=/{n=$0} /^H: Handlers=/{print n " | " $0}' /proc/bus/input/devices | cut -c1-150
echo "--- how was the game launched at 20:17Z? (KWin foreground_booster / Steam game launch lines)"
journalctl --user --since "20:10" --until "20:30" -o short-iso 2>/dev/null | grep -i -E "foreground_booster|killemall|launch-|GameAction|AppID" | cut -c1-200 | tail -12
echo "--- Steam logs: game launches today (shortcut app ids)"
for f in ~/.steam/steam/logs/console_log.txt ~/.steam/steam/logs/content_log.txt; do [ -f "$f" ] && grep -h "$(date -u +%Y-%m-%d)" "$f" | grep -i -E "launch|GameAction|killemall" | tail -6 | cut -c1-200; done
echo "--- desktop launchers for the game"
grep -l -i killemall ~/.local/share/applications/*.desktop ~/Desktop/*.desktop 2>/dev/null
for f in $(grep -l -i killemall ~/.local/share/applications/*.desktop ~/Desktop/*.desktop 2>/dev/null); do echo "== $f"; grep -E "^(Name|Exec)=" "$f"; done
echo "--- Steam shortcuts (python parse of shortcuts.vdf: names + exe)"
python3 - <<'EOF' 2>/dev/null || echo "python parse failed"
import re,glob
for f in glob.glob("/home/alex/.steam/steam/userdata/*/config/shortcuts.vdf"):
    b=open(f,"rb").read()
    for m in re.finditer(rb"\x01AppName\x00([^\x00]*)\x00\x01Exe\x00([^\x00]*)\x00", b, re.I):
        print(m.group(1).decode(errors="replace"), "->", m.group(2).decode(errors="replace"))
    for m in re.finditer(rb"\x02appid\x00(....)", b):
        import struct; print("appid", struct.unpack("<I", m.group(1))[0])
EOF
echo "--- Steam Input per-game layouts (controller_neptune.vdf) mentioning the game"
ls -d ~/.steam/steam/steamapps/common/Steam\ Controller\ Configs/*/config/* 2>/dev/null | grep -i -E "kill|zx|spectrum|launch" | head
for d in $(ls -d ~/.steam/steam/steamapps/common/Steam\ Controller\ Configs/*/config/* 2>/dev/null | grep -i -E "kill|zx|spectrum|launch" | tr ' ' '?' ); do
  for v in $d/controller_neptune.vdf; do
    [ -f "$v" ] || continue
    echo "== $v ($(stat -c '%y' "$v" | cut -c1-19))"
    grep -n -E "\"(title|description|controller_type|button_shoulder|left_trigger|right_trigger|mode|binding)\"" "$v" | cut -c1-160 | head -60
  done
done
echo "--- ZEsarUX log around the 20:17Z launch: joystick / key lines"
awk '/2026-11-03T20:17/{p=1} p' ~/.local/state/deck/killemall.log 2>/dev/null | grep -v -E "^\s*$" | grep -i -E "joystick|realjoystick|key|event|error|warning|tape|Opening|cannot|not" | cut -c1-160 | head -20
echo "--- ZEsarUX log: full text after the 20:17Z launch line (first 25 non-empty lines)"
awk '/2026-11-03T20:17/{p=1} p' ~/.local/state/deck/killemall.log 2>/dev/null | grep -v -E "^\s*$" | head -25 | cut -c1-160
echo "--- python evdev available on the Deck? (for an end-to-end pad test later)"
python3 -c "import evdev; print('evdev', evdev.__version__)" 2>&1 | head -1
ls -l /dev/uinput 2>&1
date -u +%H:%MZ
