#!/bin/bash
# m22_survey22.sh - READ-ONLY: facts needed for the floor-band + key-default change (M2.3)
cd ~/work/killemall
echo "--- stack / IM2 layout"
grep -nE 'ld sp,|65008|0xFDF0|im 2|im2|IM2|0xFDFD|65021|ld i,|0xFE00|65024' src/48k/kea48.asm | head -12
awk '{v=$3; sub(/H$/,"",v); a=strtonum("0x" v); if (a>=0xFD00) printf "%s %04X\n",$1,a}' build/kea48.sym | sort -k2 | head -20
echo "--- exx / alternate set users"
grep -nE "\bexx\b" src/48k/kea48.asm src/48k/gen/tables48.asm src/common/*.asm | head -12
echo "--- cell_ptr / cell_at register use"
sed -n "$(grep -n '^cell_ptr:' src/48k/kea48.asm | cut -d: -f1),+14p" src/48k/kea48.asm
echo "--- game_a.asm movement calls"
sed -n 1,40p src/common/game_a.asm
echo "--- DRAM init (who zeroes 0x5D00..)"
grep -nE 'DRAM|0x5D00|23808' src/48k/kea48.asm src/common/*.asm | head -8
echo "--- render entry around rp_y + CLRBUF generated code"
sed -n "$(grep -n '^CLRBUF:' src/48k/gen/tables48.asm | cut -d: -f1),+12p" src/48k/gen/tables48.asm
grep -nE '^cl_|^CLRBUF|cl_col|cl_sp' src/48k/gen/tables48.asm | head
echo "--- chk48/test48 floor handling"
grep -nE 'floor|0x55|0xAA|48|rows|mask' tools/chk48.py | head -12
echo "--- gates list"
grep -nE 'python|bash' tools/t6_gates.sh | head -12
echo "--- hint / message strings mentioning keys"
grep -nE '"[^"]*(SPACE|FIRE|OPEN| M |M=|USE)[^"]*"' src/common/*.asm | head -12
