#!/bin/bash
# M2.4 survey 4: run-list emission in gen48, weapon draw, tests' sprite expectations, dead-code candidates (read-only)
cd ~/work/killemall || exit 1
echo "== gen48 sprite section"; sed -n 257,335p tools/gen48.py
echo "== hud_b draw_weapon"; sed -n 25,79p src/common/hud_b.asm
echo "== in_begin/in_end region"; grep -n "in_begin\|in_end\|fe_frame\|fe_begin\|fe_end" src/common/input.asm src/common/frontend.asm | head
echo "== test_sprite_scale expectations"; grep -nE "def |assert|check\(|changed|width|height|cols|bbox" tools/test_sprite_scale.py | head -40
echo "== test_game_sprites checks"; sed -n 40,140p tools/test_game_sprites.py | grep -nE "check|assert|changed|span|zbuf|print" | head -30
echo "== m23_gates list"; cat tools/m23_gates.sh; cat tools/t6_gates.sh | head -20
