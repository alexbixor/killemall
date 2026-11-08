#!/bin/bash
# m22_survey20.sh - READ-ONLY: memory map facts for the floor-texture change (gaps, low block slack, wall_height, key tests)
cd ~/work/killemall
echo "--- symbols in 0x5B00..0x6D00 and low block end"
awk '{v=$3; sub(/H$/,"",v); a=strtonum("0x" v); if (a>=0x5B00 && a<0x6D00) printf "%s %04X\n",$1,a}' build/kea48.sym | sort -k2 | head -40
echo "--- low block: SCHAIN_END, level_data size, first free low"
grep -nE 'level_data|SCHAIN_END|low_end|lo_end|LOW_END|^\s*org' src/48k/kea48.asm src/48k/gen/sprites48.asm 2>/dev/null | head -12
grep -nE 'level_data|lo_end|low_end|32767|32768|hi_end|free' tools/build_m22_48.sh tools/m22_build_report.sh build/m22_build_last.log | head -20
echo "--- wall_height / K"
grep -nE 'def wall_height|def even_height|K *=|HORIZ|^H *=|FOCAL' tools/gen48.py | head; sed -n "$(grep -n 'def wall_height' tools/gen48.py | cut -d: -f1),+6p" tools/gen48.py
echo "--- in_keys defaults + tests mentioning keys"
grep -nE '^in_keys|defb 0x[0-9A-Fa-f]+,0x[0-9A-Fa-f]+ *;' src/common/input.asm | head -12
grep -nE '"M"|\bM\b.*fire|SPACE.*(fire|open|use)|keys\(\[' tools/test_game_hud.py tools/test_frontend.py tools/test_sprite_scale.py tools/m22_shots.py tools/test_128.py 2>/dev/null | head -20
echo "--- move_by call sites (fwd/back/strafe)"
grep -nE 'call move_by|move_by' src/common/game*.asm src/48k/kea48.asm | head -8
