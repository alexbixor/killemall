#!/bin/bash
# m22_survey18.sh - read-only: sprite-scale test expectations, new_game stats reset, level 3 'm', depth test in sprites_f, 128 ROM FF
cd ~/work/killemall
echo "== test_sprite_scale set_thing / expectations"; grep -n "set_thing\|expect\|assert\|FAIL\|hv\b\|floor\|def " tools/test_sprite_scale.py | head -40
echo "== test_game_sprites set_thing types"; grep -n "set_thing(m" tools/test_game_sprites.py tools/test_game_enemies.py tools/test_game_doors.py | head
echo "== kea48 new_game 60-84"; sed -n 60,84p src/48k/kea48.asm
echo "== level 3 header + m"; head -3 assets/levels/03_furnace.txt; grep -n "m" assets/levels/03_furnace.txt | grep -v "^1:" | head -3
echo "== sprites_f 1-60 (depth test)"; sed -n 1,60p src/common/sprites_f.asm
echo "== 128 rom"; ls tools/zesarux/*.rom; python3 -c "
import glob
for f in glob.glob('tools/zesarux/*.rom'):
    r=open(f,'rb').read()
    n=len(r)//256
    print(f, len(r), [hex(p) for p in range(n) if r[p*256:(p+1)*256]==b'\xff'*256][:12])"
echo "== make128 anchors"; grep -n "replace\|anchor\|assert" tools/make128.py | head -30
