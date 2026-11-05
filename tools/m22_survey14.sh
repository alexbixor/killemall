#!/bin/bash
# m22_survey14.sh - read-only facts before writing hud.asm: print users, wall ink table, level letters, load_level ROM use, build steps
cd ~/work/killemall
echo "== print/print_char users outside hud"; grep -n "call print\b\|jp print\b\|call print_char\|jp print_char\|call print_num" src/common/*.asm src/48k/kea48.asm | grep -v "^src/common/hud"
echo "== CODEINK / wall ink"; grep -n "CODEINK\|def wall_ink\|INK = \|ink =" tools/gen48.py | head; grep -n -A2 "^CODEINK" src/48k/gen/tables48.asm | head -5
echo "== mapc letters"; grep -n "'[a-zA-Z]': *[0-9]\|\"[a-zA-Z]\": *[0-9]\|THING\|types" tools/mapc.py | head -20
echo "== level 1 map"; cat assets/levels/01_entry.txt
echo "== load_level"; awk '/^load_level:/{f=1} f{print; n++} n>40{exit}' src/48k/kea48.asm
echo "== build_m2_48 steps"; cat tools/build_m2_48.sh
echo "== sprites_e 40-75 (top/step)"; sed -n 40,75p src/common/sprites_e.asm
echo "== sprites_d hv/c0/nc"; grep -n "hv\|NCTAB\|STEPTAB\|VSTEP\|wall_height\|HTAB" src/common/sprites_d.asm | head -30
echo "== vis entry layout"; sed -n 1,12p src/common/sprites_d.asm
