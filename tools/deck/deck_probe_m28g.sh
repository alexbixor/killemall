#!/bin/bash
# deck_probe_m28g.sh - READ-ONLY (runs ON the Deck via 'bash -s'): keyboard LAYOUT state. The watcher proved Z/X arrive as
# key codes 44/45 on Sunshine's virtual keyboard (the same device that delivers SPACE and the arrow keys, which work), so the
# loss is between the kernel event and the emulated Spectrum matrix. Suspect: KDE layout list "gr,us" -> letters reach the
# X11 emulator as Greek keysyms (zeta/chi), arrows and space are layout-independent.
set -u
echo "deck time $(date -u +%H:%M:%SZ)"
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
echo "--- ~/.config/kxkbrc (whole file)"
cat ~/.config/kxkbrc 2>/dev/null
echo "--- current KDE layout (index into LayoutList; 0 = first)"
qdbus6 org.kde.keyboard /Layouts getLayout 2>&1 | head -2
qdbus6 org.kde.keyboard /Layouts getLayoutsList 2>&1 | head -4
echo "--- Xwayland displays + their current xkb layout/group as X11 apps see it"
for s in /tmp/.X11-unix/X*; do
  d=":${s##*/X}"
  echo "display $d: $(DISPLAY=$d timeout 5 setxkbmap -query 2>&1 | tr '\n' ' ')"
  DISPLAY=$d timeout 5 xkbcomp $d - 2>/dev/null | grep -m1 -E "xkb_symbols" | cut -c1-160
done
echo "--- KWin: layout policy env / xkb group state"
grep -rE "SwitchMode|LayoutLoopCount|ShowSingle|Options" ~/.config/kxkbrc 2>/dev/null
echo "--- last 3 layout switches in the journal (kded keyboard / kwin)"
journalctl --user -o short-iso --since "-3h" 2>/dev/null | grep -iE "layout|xkb" | tail -3 | cut -c1-160
date -u +%H:%M:%SZ
