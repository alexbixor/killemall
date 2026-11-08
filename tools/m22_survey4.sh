#!/bin/bash
# m22_survey4.sh - read-only: RAM-only defs that could leave the tape image, weapon var, 128K include handling
cd ~/work/killemall
echo "== defs in common/48k sources (RAM-only blocks)"; grep -n "defs" src/common/*.asm src/48k/kea48.asm | grep -v "^src/common/stubs"
echo "== weapon var"; grep -n "^weapon\|weapon:\|(weapon)\|cur_weapon\|wpn" src/common/game_*.asm src/common/state.asm | head -12
echo "== make128 gen handling"; grep -n "gen/\|include\|replace\|tables\|sprites48" tools/make128.py | head -20
echo "== build128"; cat tools/build128.sh | head -30
echo "== pasmo version + directives"; pasmo --version 2>&1 | head -2; grep -rn "\.error\|^ *if \|IF \$" src/common/*.asm src/48k/kea48.asm | head -5
echo "== 128k gen dir"; ls src/128k src/128k/gen 2>/dev/null | head -20
echo "== zbuf/vis/things/nvis defs context"; grep -n "^zbuf\|^vis\|^things\|^nvis\|^ds_hv\|^ds_c\b" src/common/*.asm
echo "== low block end"; grep -E "^(level_data|hi_end)\s" build/kea48.sym; python3 -c "print('low spare', 32768-(0x7B3B+1081))"
echo "== stack depth probe: calls in game_tick chain"; grep -c "call\|push" src/common/game_e.asm src/common/beeper.asm | head
