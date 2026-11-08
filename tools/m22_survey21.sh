#!/bin/bash
# m22_survey21.sh - READ-ONLY: memory map gaps, dead-area tables, tap loader, ray FOV, fire/break order, key hint strings
cd ~/work/killemall
echo "--- dead area + low block symbols sorted, with gaps"
awk '{v=$3; sub(/H$/,"",v); a=strtonum("0x" v); if (a>=0x5C00 && a<0x8200) printf "%08d %s %04X\n",a,$1,a}' build/kea48.sym | sort -n | awk 'NR>1 && $1-prev>0 {printf "   gap %5d B\n",$1-prev} {print $2, $3; prev=$1}' | head -60
echo "--- FTX/FTY/ATTRBUF/BUF/DRAM definitions"
grep -nE '^(FTX|FTY|ATTRBUF|BUF|DRAM|ATTRWIN|SOLID|SOLIDPG)\b|equ 0x6|equ 2[4-7][0-9]{3}' src/48k/kea48.asm src/common/state.asm tools/gen48.py | head -20
echo "--- tap builder: CLEAR / loader BASIC / block list"
grep -nE 'CLEAR|LOAD|basic|BASIC|def tap|def write_tap|27904|27903|code_block|raw_block' tools/gen48.py tools/mktap*.py tools/build_m22_48.sh 2>/dev/null | head -30
ls tools/*.py | tr '\n' ' '; echo
echo "--- ray setup: FOV / per-column angle step / plane"
grep -nE 'FOV|fov|ANGSTEP|col.*angle|angle.*col|RAYANG|RAYTAB|CAMX|PLXTAB|PLYTAB' tools/gen48.py src/48k/kea48.asm | head -16
echo "--- game loop: break vs fire order, shoot"
grep -nE 'in_break|bit 4,|and 0x10|fire|shoot|call fe_pause' src/common/game_a.asm | head -16
echo "--- door_log / DRAM init"
grep -nE 'door_log|DRAM' src/48k/kea48.asm src/common/game_b.asm src/common/game_a.asm | head -10
echo "--- key hint strings in frontend"
grep -nE 'defb ".*(SPACE|FIRE|OPEN|USE|Q A O P|QAOP|M=|M ).*"' src/common/frontend.asm src/common/hud*.asm | head -12
echo "--- CLRBUF timing + opt_detail uses"
grep -nE 'opt_detail|apply_opts' src/48k/kea48.asm src/common/*.asm | head -12
