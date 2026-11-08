#!/bin/bash
# m22_survey19.sh - read-only: FE_ANORM, fe test link set, 128K ROM 1 FF pages, pickups filter, print_char callers
cd ~/work/killemall
echo "== FE_ANORM / FE_PIX"; grep -n "FE_ANORM\s*equ\|FE_PIX\s*equ\|FE_ATTR\s*equ" src/common/frontend.asm
echo "== fe_build includes"; cat tools/fe_build.sh | head -20; grep -n "include" tools/fe_test_main.asm | head -20
echo "== stubs hud"; grep -n "hud\|print" src/common/stubs.asm src/common/fe_stubs.asm 2>/dev/null | head
echo "== 128.rom ROM1 FF pages"; python3 -c "
r=open('tools/zesarux/128.rom','rb').read(); r1=r[16384:32768]
print('rom1 FF pages', [hex(p) for p in range(64) if r1[p*256:(p+1)*256]==b'\xff'*256])
r48=open('tools/zesarux/48.rom','rb').read()
print('rom1 == 48.rom:', r1==r48, 'diff bytes', sum(1 for a,b in zip(r1,r48) if a!=b))"
echo "== game_c 1-16"; sed -n 1,16p src/common/game_c.asm
echo "== print_char callers"; grep -n "print_char" src/common/*.asm src/48k/kea48.asm | grep -v "^src/common/hud"
echo "== level_data end vs 32768"; python3 -c "print('low free', 32768 - (0x7B09 + 1081))"
echo "== kea48 940-950"; sed -n 936,950p src/48k/kea48.asm
echo "== build_m22_48.sh"; cat tools/build_m22_48.sh
