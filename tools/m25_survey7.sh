#!/bin/bash
# m25_survey7.sh - read-only: floor.asm, perp_h, gen48 sprites48/runs16, 128K sources, gates/build scripts, test heads
cd ~/work/killemall || exit 1
echo "== floor.asm"; cat src/common/floor.asm
echo "== perp_h + HTAB users"; grep -nE "perp_h|HTABN|HTABF|CLIPSET" src/48k/kea48.asm tools/gen48.py | head -20
awk '/^perp_h:/,/ret$/' src/48k/kea48.asm | head -60
echo "== gen48 head (constants)"; sed -n 1,32p tools/gen48.py
echo "== gen48 sprites48 + runs16"; sed -n 257,329p tools/gen48.py
echo "== 128K sources"; ls src/128k/ 2>/dev/null; grep -nE "include|BUF|ATTRWIN|org|equ" src/128k/*.asm 2>/dev/null | head -40
echo "== build_m24_48.sh"; cat tools/build_m24_48.sh
echo "== m24_gates.sh"; cat tools/m24_gates.sh
echo "== test_128.py head"; sed -n 1,25p tools/test_128.py
echo "== sprites_b.asm"; cat src/common/sprites_b.asm
echo "== frontend screen refs"; grep -nE "0x4|0x5[0-9A-F]{3}|225|ATTR|cls|window|frame" src/common/frontend.asm | head -30
echo "== isr"; sed -n 150,170p src/48k/kea48.asm
echo "== cls/menu_bg"; grep -nE "^cls:|^menu_bg:|^new_game:|^apply_opts:" src/48k/kea48.asm src/common/*.asm
