#!/bin/bash
# m22_survey9.sh - read-only: test48 flow (init_game?), chk48 floor detection, pickups filter, geo48 script
cd ~/work/killemall
echo "== test48.py key funcs"; grep -n "def \|init_game\|render\|sp = \|0x6A\|set_memory_block" tools/test48.py | head -30
echo "== geo48.sh"; cat tools/geo48.sh
echo "== chk48 measured_heights"; sed -n 43,60p tools/chk48.py
echo "== pickups filter"; sed -n 1,30p src/common/game_c.asm
echo "== game_e damage context"; sed -n 90,115p src/common/game_e.asm
echo "== runs16"; sed -n 258,290p tools/gen48.py
