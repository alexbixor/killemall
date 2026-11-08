#!/bin/bash
# m23_survey4.sh - READ-ONLY: how harnesses load the image (0xFF01 code region viability), test48 setup, zes helpers
cd ~/work/killemall
echo "--- test_game_sprites machine()"; grep -n -A14 '^def machine' tools/test_game_sprites.py | head -30
echo "--- test48 setup (posx/angle pokes)"; grep -n -iE 'posx|posy|angle|load|tap|bin|render|frames' tools/test48.py | head -20
echo "--- m22_stack gap logic"; sed -n 20,45p tools/m22_stack.py
echo "--- t6_zes helpers"; grep -n -E 'def ' tools/t6_zes.py
echo "--- m22_shots menu/keys usage"; grep -n -iE 'press|key|screenshot|png|menu|start' tools/m22_shots.py | head -30
echo "--- mktap48 code block handling"; sed -n 55,80p tools/mktap48.py
echo "--- state.asm DRAM_END line + fe vars"; grep -n -E 'DRAM_END|fe_tmpk' src/common/state.asm
echo "--- fake_input helper"; grep -rn -A6 'def fake_input' tools/test_game_sprites.py tools/test_game_enemies.py | head -12
echo "--- kea48 lines 44-60 main loop"; sed -n 44,60p src/48k/kea48.asm