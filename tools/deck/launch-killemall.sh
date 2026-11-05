#!/bin/bash
# launch-killemall.sh - Kill'em all (ZX Spectrum 48K) in ZEsarUX, full screen, Deck pad drives the game.
# Usage: launch-killemall.sh [tape.tap]   (default: newest killemall48_*.tap in ~/Emulation/roms/zxspectrum)
# Pad (Steam Input virtual X-Box pad): left stick fwd/back + strafe, right stick turn, d-pad fwd/back/turn, A fire,
#      B or X open door, L1/R1 strafe, Y = Enter, START = CAPS SHIFT (START+B = BREAK = pause menu), SELECT = emulator menu.
# Keyboard always works: Q A O P M SPACE Z X, CAPS+SPACE pause, F5/ESC emulator menu. --vo sdl: xwindows under Xwayland drops letter keys (3 Nov 2026). KEA_HEADLESS=1 -> 8 s no-window self-test.
cd ~/Applications/zesarux || exit 1
export LD_LIBRARY_PATH=~/Applications/zesarux/libs
ROMS=~/Emulation/roms/zxspectrum
TAP=${1:-$(ls -t "$ROMS"/killemall48_*.tap 2>/dev/null | head -1)}
[ -f "$TAP" ] || { echo "no tape: $TAP"; exit 2; }
JS=/dev/input/js0
for j in /dev/input/js*; do
  n=$(cat "/sys/class/input/${j##*/}/device/name" 2>/dev/null)
  case "$n" in *X-Box*|*Steam*|*Xbox*) JS=$j; break;; esac
done
if [ -n "$KEA_HEADLESS" ]; then VID=(--vo null --ao null --exit-after 8); else VID=(--vo sdl --ao pulse --fullscreen --zoom 3 --hidemousepointer); fi
mkdir -p ~/.local/state/deck
echo "$(date -u +%FT%TZ) tape=$TAP js=$JS headless=${KEA_HEADLESS:-0}" >> ~/.local/state/deck/killemall.log
# Measured on ZEsarUX 13.0 (tools/m22_pad_test.py, virtual clone of the Deck pad): the event table keeps ONE source per
# event and the key table takes at most ~12 live entries, so: sticks -> events -> emulated "OPQA Space" joystick
# (Up=Q Down=A Left=O Right=P Fire=SPACE = game fire since M2.3), everything else -> button/axis-to-key table. Game must stay on its default
# keys (Q A O P SPACE M Z X, CONTROLS = KEYBOARD) - do not REDEFINE KEYS when playing with the pad.
# keys: 113 q fwd, 97 a back, 111 o left, 112 p right, 32 space fire, 109 m open (M2.3), 122 z / 120 x strafe, 13 enter, 128 caps
exec ./zesarux --noconfigfile --machine 48k "${VID[@]}" \
  --nosplash --nowelcomemessage --disable-all-first-aid --quickexit \
  --joystickemulated "OPQA Space" --realjoystickpath "$JS" --cleareventlist \
  --joystickevent -1 Up --joystickevent +1 Down --joystickevent -3 Left --joystickevent +3 Right \
  --joystickevent 1 Fire --joystickevent 6 EscMenu \
  --joystickkeybt -0 122 --joystickkeybt +0 120 --joystickkeybt -6 111 --joystickkeybt +6 112 \
  --joystickkeybt -7 113 --joystickkeybt +7 97 --joystickkeybt 0 32 --joystickkeybt 2 109 \
  --joystickkeybt 3 13 --joystickkeybt 4 122 --joystickkeybt 5 120 --joystickkeybt 7 128 \
  "$TAP" >> ~/.local/state/deck/killemall.log 2>&1
