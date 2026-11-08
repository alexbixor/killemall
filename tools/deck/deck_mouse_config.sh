#!/bin/bash
# Deck: add Kempston mouse emulation to the 128K ZEsarUX launcher (the 128K tape has MOUSE: OFF/ON since lane M).
# Backup first; idempotent; verifies with a headless 8 s launch.
set -e
L=~/.local/bin/launch-killemall128
TS=$(date -u +%Y%m%d-%H%M%S)
if grep -q "enablekempstonmouse" "$L"; then echo "already configured"; else
  cp "$L" "$L.bak-mouse-$TS"
  # insert the mouse flags after the --quickexit line; sens 2 = 0.67 counts/px (lane M measured 0.333 at sens 1; sens 4 flips sign)
  sed -i 's|  --nosplash --nowelcomemessage --disable-all-first-aid --quickexit \\|  --nosplash --nowelcomemessage --disable-all-first-aid --quickexit \\\n  --enablekempstonmouse --kempstonmouse-sens 2 --ignoremouseclickopenmenu --disablemenumouse \\|' "$L"
  sed -i 's|^# Keyboard always works:|# Mouse (8 Nov 2026): Kempston mouse emulated (game menu MOUSE: ON; left = fire, right = open). Clicks never open the emulator\n#      menu (--ignoremouseclickopenmenu --disablemenumouse): use SELECT / F5 / ESC for it. ZEsarUX 13 cannot grab the pointer,\n#      so a long turn stops at the screen edge - move the mouse back and continue (Fuse grabs the pointer, ZEsarUX does not).\n# Keyboard always works:|' "$L"
  echo "patched; backup $L.bak-mouse-$TS"
fi
grep -n "kempston" "$L" | cut -c1-120
bash -n "$L" && echo "syntax ok"
KEA_HEADLESS=1 timeout 30 "$L" >/dev/null 2>&1; echo "headless launch rc=$?"
tail -1 ~/.local/state/deck/killemall128.log | cut -c1-120
grep -i "mouse" ~/.local/state/deck/killemall128.log | tail -2 | cut -c1-120
pgrep -x zesarux >/dev/null && echo "WARNING zesarux still running" || echo "no zesarux left running"
