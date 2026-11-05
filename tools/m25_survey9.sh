#!/bin/bash
# m25_survey9.sh - read-only: init_game/new_game/apply_opts, game_b MOV use, pixdata gen, oracles heads, refcast 0.66, t6_gates
cd ~/work/killemall || exit 1
echo "== kea48 61-200 (new_game, apply_opts, menu_bg, load_level, init_game)"; sed -n 61,200p src/48k/kea48.asm
echo "== game_b.asm 1-40"; sed -n 1,40p src/common/game_b.asm
echo "== game_a.asm"; cat src/common/game_a.asm
echo "== m22_pixdata.py"; cat tools/m22_pixdata.py
echo "== 0.66 / 48.5 / plane users in tools+src"; grep -nE "0\.66|48\.5|plane" tools/*.py src/common/*.asm src/48k/kea48.asm | grep -v m25_mock | head -30
echo "== t6_gates.sh"; cat tools/t6_gates.sh
echo "== geo48"; cat tools/geo48.sh 2>/dev/null | head -30
echo "== gen48 33-60"; sed -n 33,60p tools/gen48.py
echo "== gen48 20-32 docstring tail"; sed -n 20,32p tools/gen48.py
