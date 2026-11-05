#!/bin/bash
# m22_survey15.sh - read-only: fe_clr_bottom, print context, ROMFONT, message texts, m22_pixdata tables
cd ~/work/killemall
echo "== kea48 97-125"; sed -n 97,125p src/48k/kea48.asm
echo "== fe_clr_bottom"; grep -n -A14 "^fe_clr_bottom:" src/common/frontend.asm | head -18
echo "== ROMFONT"; grep -n "ROMFONT\s*equ" src/48k/kea48.asm src/common/*.asm
echo "== message texts"; grep -n "defb \"" src/common/game_*.asm src/common/frontend.asm src/48k/kea48.asm | grep -v "lbl_" | head -20
echo "== pixdata script"; cat tools/m22_pixdata.py
echo "== ROM FF pages"; python3 -c "
r=open('tools/zesarux/48.rom','rb').read()
print([hex(p) for p in range(64) if r[p*256:(p+1)*256]==b'\xff'*256])"
echo "== 128K rom paging"; grep -n "7FFD\|0x7ffd\|32765" src/128k/*.asm tools/make128.py 2>/dev/null | head -8
echo "== levels 2/3 m usage"; grep -c "m" assets/levels/02_barracks.txt assets/levels/03_furnace.txt; grep -n "^#" assets/levels/02_barracks.txt | head -2
