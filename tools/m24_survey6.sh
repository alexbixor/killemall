#!/bin/bash
# M2.4 survey 6: dead-code candidates, silhouette test mechanics, remaining sprite art (read-only)
cd ~/work/killemall || exit 1
echo "== input.asm 18-40 (in_begin region)"; sed -n 18,40p src/common/input.asm; grep -rn "in_begin\|in_end" src tools/*.py | grep -v "input.asm:22\|input.asm:188" | head -5
echo "== test_sprite_scale silhouette/attrs/main"; sed -n 20,70p tools/test_sprite_scale.py
echo "== test_sprite_scale main loop"; sed -n 70,135p tools/test_sprite_scale.py
echo "== test_game_sprites buf/changed_columns"; sed -n 40,60p tools/test_game_sprites.py; grep -n "def buf\|def changed_columns\|def fake_input\|def load_code\|def run_until" tools/test48.py tools/test_game_sprites.py
echo "== imp art"; cat assets/sprites/01_imp_walk_b.txt assets/sprites/02_imp_attack.txt assets/sprites/03_imp_dead.txt
echo "== game_e enemies state machine: states and anim"; grep -n "state\|attack\|dead\|anim\|timer" src/common/game_e.asm | head -30
