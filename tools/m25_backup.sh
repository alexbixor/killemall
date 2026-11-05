#!/bin/bash
# m25_backup.sh - snapshot everything M2.5 may touch, before any edit
cd ~/work/killemall || exit 1
mkdir -p build/pre_m25
tar czf build/pre_m25/src_pre_m25.tgz src tools/gen48.py tools/test48.py tools/chk48.py tools/test_frontend.py tools/deck \
    tools/spritec.py tools/test_sprite_card.py tools/test_sprite_scale.py tools/test_game_sprites.py tools/test_floor_lines.py \
    tools/m22_stack.py tools/t6_gates.sh tools/m24_gates.sh tools/build_m24_48.sh 2>/dev/null
tar czf build/pre_m25/assets_pre_m25.tgz assets
ls -l build/pre_m25/
tar tzf build/pre_m25/src_pre_m25.tgz | wc -l
sha256sum build/killemall48_m24.tap build/killemall48_m23.tap | cut -c1-16,65-
