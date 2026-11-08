#!/bin/bash
# m22_survey13.sh - read-only: exact snippets needed to write the dashboard (clr_rows13, cls, print, pickups, damage, wall inks, mul168)
cd ~/work/killemall
echo "== kea48 84-96"; sed -n 84,96p src/48k/kea48.asm
echo "== kea48 155-172 (cls)"; sed -n 155,172p src/48k/kea48.asm
echo "== print full"; awk '/^print:/{f=1} f{print; n++} n>26{exit}' src/48k/kea48.asm
echo "== game_c 40-84 (pickup_item)"; sed -n 40,84p src/common/game_c.asm
echo "== game_e 98-116 (enemy hit)"; sed -n 98,116p src/common/game_e.asm
echo "== game_d 1-35"; sed -n 1,35p src/common/game_d.asm
echo "== gen48 wall inks 164-196"; sed -n 164,196p tools/gen48.py
echo "== mul168"; sed -n 41,56p src/common/sprites.asm
echo "== pixdata"; .venv/bin/python tools/m22_pixdata.py 2>&1 | head -60
echo "== sprite list"; grep -n "^spr_\|sprite_names\|SPRITES = \|^[0-9][0-9]_" tools/spritec.py | head -5; ls assets/sprites | head -40
