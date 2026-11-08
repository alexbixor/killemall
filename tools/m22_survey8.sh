#!/bin/bash
# m22_survey8.sh - read-only: pickups, state.asm, sprite-scale test expectations, geo compare method, write-hook tests
cd ~/work/killemall
echo "== state.asm"; cat src/common/state.asm
echo "== game_c pickups 30..82"; sed -n 30,82p src/common/game_c.asm
echo "== levels with m"; grep -c "m" assets/levels/0[123]_*.txt; grep -n "^#" assets/levels/02_barracks.txt assets/levels/03_furnace.txt | head -4
echo "== test_sprite_scale asserts"; grep -n "assert\|expect\|hv\|FAIL\|def " tools/test_sprite_scale.py | head -40
echo "== chk48 compare"; grep -n "def \|mismatch\|texel\|band\|top\|bottom" tools/chk48.py | head -20
echo "== write hooks / address range checks in tests"; grep -n "0x5[89A-F]\|write_callback\|set_write\|wrprobe\|0x6000\b" tools/test_*.py tools/t6_gates.sh tools/geo48.sh | head -20
echo "== machine() in test_game_sprites"; grep -n "def machine\|load\|set_memory_block\|tap" tools/test_game_sprites.py | head -20
