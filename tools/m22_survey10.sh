#!/bin/bash
# m22_survey10.sh - read-only: mul168 registers, 'm' thing meaning, hud test details, level 3 'm'
cd ~/work/killemall
echo "== mul168"; sed -n 41,56p src/common/sprites.asm
echo "== mapc thing legend"; sed -n 6,12p tools/mapc.py
echo "== level3 m"; grep -n "m" assets/levels/03_furnace.txt | head -3
echo "== test_sprite_scale 53..100"; sed -n 53,100p tools/test_sprite_scale.py
echo "== test_game_enemies hud/health refs"; grep -n "health\|hud\|row_text\|0x48\|0x50" tools/test_game_enemies.py tools/test_game_doors.py tools/test_game_sprites.py | head -20
