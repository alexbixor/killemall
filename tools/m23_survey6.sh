#!/bin/bash
# m23_survey6.sh - READ-ONLY: multiply helpers, slot mask C in ray, load_code, zes png, sprite_scale floor dependence
cd ~/work/killemall
echo "--- mul helpers"; grep -n -iE '^mul|mul8|mul16|squares|SQLO' src/48k/kea48.asm | head -20
echo "--- slot mask C / band call (kea48 640..700)"; sed -n 640,700p src/48k/kea48.asm
echo "--- test48 load_code"; sed -n 16,40p tools/test48.py
echo "--- t6_zes png/grab"; sed -n 55,70p tools/t6_zes.py
echo "--- sprite_scale: how it finds sprite rows"; grep -n -iE 'BUF|0x6000|pixel|row' tools/test_sprite_scale.py | head -20
echo "--- test_game_hud floor/BUF refs"; grep -n -iE '0x6000|BUF\b' tools/test_game_hud.py | head
echo "--- demo tool key/moves"; sed -n 12,60p tools/t6_demo.py