#!/bin/bash
# m25_survey10.sh - read-only facts needed for the M2.5 memory plan
cd ~/work/killemall || exit 1
S=build/kea48_m24.sym
echo "== sym: clear/copy/attr/render/frame symbols"
for s in CLRBUF cl_de cl_fl cl_sp COPYBUF cb_col cb_sp ATTRCOPY ATTR_1 ATTR_6 ATTRTAB render draw_things frame_end fl_set hi_end SPG NCTAB STEPTAB VSTEP SCHAIN SCHAIN_END spr_table level_data start FTX FTY ATTRBUF BUF SOLIDPG CHJ TEX CODEINK BANDTAB; do
  printf "%-10s %s\n" $s "$(grep -E "^$s\s+EQU" $S | head -1)"
done
echo "== frame order (kea48.asm 376-440)"; sed -n 376,440p src/48k/kea48.asm
echo "== MOV table users: kea48 212-262"; sed -n 212,262p src/48k/kea48.asm
echo "== game_b.asm 1-40"; sed -n 1,40p src/common/game_b.asm
echo "== PLX users kea48 322-376"; sed -n 322,376p src/48k/kea48.asm
echo "== gen48 table formulas"; grep -nE "PLXTAB|PLYTAB|MOVXTAB|MOVYTAB|0\.66|SPEED|speed|38|FTX|FTY|SPG|NCTAB|STEPTAB|VSTEP|def gen_|def emit_|HTABN|HTABF|RECIP" tools/gen48.py | head -60
echo "== FTX/FTY users"; grep -nE "FTX|FTY" src/48k/kea48.asm src/common/*.asm | grep -v "^\S*:\s*;" | head -30
echo "== ATTRBUF users"; grep -nE "ATTRBUF" src/48k/kea48.asm src/common/*.asm tools/gen48.py | head -30
echo "== CLRBUF gen (unrolled48.asm head 1-60)"; sed -n 1,60p src/48k/gen/unrolled48.asm
echo "== COPYBUF gen"; awk '/^COPYBUF:/,/^ATTRCOPY:/' src/48k/gen/unrolled48.asm | head -40
echo "== ATTRCOPY gen"; awk '/^ATTRCOPY:/,0' src/48k/gen/unrolled48.asm | head -30
echo "== ISR"; grep -nE "ISRVEC|TABLE|im 2|im 1|ticks|frames" src/48k/kea48.asm | head -20
