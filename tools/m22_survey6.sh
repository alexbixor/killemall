#!/bin/bash
# m22_survey6.sh - read-only: print routines, 128K ROM paging, THSPR, damage path, level thing format, vis_add
cd ~/work/killemall
echo "== fe_print"; awk '/^fe_print:/{f=1} f{print; n++} n>30{exit}' src/common/frontend.asm
echo "== 128.rom FF pages per half"; python3 -c "
r=open('tools/zesarux/128.rom','rb').read(); print(len(r))
for h in range(2):
    rom=r[h*16384:(h+1)*16384]; print(' rom',h,[hex(p) for p in range(64) if rom[p*256:(p+1)*256]==b'\xff'*256])"
echo "== shim128 paging"; grep -n "7FFD\|0x7ffd\|32765\|bank_init\|out (c)\|BANKM\|rom" src/128k/shim128.asm | head -12
echo "== THSPR"; grep -n "THSPR" src/common/sprites_b.asm | head -3; awk '/^THSPR:/{print; getline; print}' src/common/sprites_b.asm
echo "== damage path"; grep -n "health" src/common/game_e.asm src/common/game_a.asm src/common/game_d.asm | head -12
echo "== level format (things)"; sed -n 1,12p assets/levels/01_entry.txt; grep -n "thing\|THING\|type" tools/mapc.py | head -15
echo "== vis_add thv use"; grep -n "thv\|tnc\|tc0\|tcx" src/common/sprites_d.asm | head
echo "== test_frontend item rows"; grep -n "text_row\|item\|row(" tools/test_frontend.py | head -20
echo "== test_game_hud rest"; sed -n 30,60p tools/test_game_hud.py
echo "== sprites48 weapons"; sed -n 290,320p tools/gen48.py
