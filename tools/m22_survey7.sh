#!/bin/bash
# m22_survey7.sh - read-only: pads, ROM FF region in the 128K ROM 1, wall code inks, frontend pause rows, stack use
cd ~/work/killemall
echo "== input.asm pad + sprites_f pad (actual)"; grep -E "^(in_keys|in_joytab|in_end|in_begin|ds_rmin|ds_cnt|ds_rmax|ds_c0|vis|nvis|things|zbuf|door_log|fe_tmpk|hud_health|msg_timer|ROWTAB)\s" build/kea48.sym
echo "== 128.rom second half 0x3900..0x3D00 content"; python3 -c "
r=open('tools/zesarux/128.rom','rb').read()[16384:]
for p in (0x38,0x39,0x3a,0x3b,0x3c):
    seg=r[p*256:(p+1)*256]; print(hex(p), 'FF count', seg.count(0xff), 'first', seg[:8].hex())
r48=open('tools/zesarux/48.rom','rb').read()
print('48 vs 128rom1 identical bytes:', sum(1 for a,b in zip(r48,r) if a==b), 'of', len(r48))"
echo "== mapc cell codes"; grep -n "CELL\|'#'\|'A'\|'B'\|code" tools/mapc.py | head -20
echo "== level1 chars used"; python3 -c "
import collections
s=open('assets/levels/01_entry.txt').read().split('\n')[1:]
c=collections.Counter(ch for l in s for ch in l if ch not in '.')
print(dict(c))"
echo "== fe_pause rows / FE_PIX FE_ATTR"; grep -n "FE_PIX\|FE_ATTR\|FE_ANORM\s*equ\|fe_pause:" src/common/frontend.asm | head
echo "== game_a hud_update call + damage"; sed -n 40,60p src/common/game_a.asm; sed -n 100,112p src/common/game_e.asm
echo "== game_d level_clear / dead"; sed -n 1,45p src/common/game_d.asm
