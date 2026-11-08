#!/bin/bash
# m22_survey3.sh - read-only facts needed for the M2.2 implementation
cd ~/work/killemall
echo "== ROM all-0xFF pages"; python3 -c "
r=open('tools/zesarux/48.rom','rb').read()
print([hex(p) for p in range(64) if r[p*256:(p+1)*256]==b'\xff'*256])"
echo "== ammo cap / health cap"; sed -n 50,66p src/common/game_c.asm
echo "== frames usage"; grep -n "frames" src/common/*.asm src/48k/kea48.asm | grep -v "^src/common/stubs" | head
echo "== ROWTAB / NCTAB / VSTEP gen"; grep -n "ROWTAB\|NCTAB\|VSTEP\|def sprites48\|24-row\|floor line\|horizon" tools/gen48.py | head -20
echo "== gates"; cat tools/t6_gates.sh | head -40
echo "== test_game_hud head"; sed -n 1,30p tools/test_game_hud.py
echo "== sprite assets"; ls assets/sprites 2>/dev/null | head -30; grep -n "sprites\|png\|txt" tools/gen48.py | sed -n 1,12p
