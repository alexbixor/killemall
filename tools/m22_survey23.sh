#!/bin/bash
# m22_survey23.sh - READ-ONLY facts before the floor-band / key-default change
cd ~/work/killemall
echo "--- high block symbol gaps >= 24 B (pads / dead space), 0xC000..0xFE00"
awk '{v=$3; sub(/H$/,"",v); a=strtonum("0x" v); if (a>=0x8000 && a<0xFE00) printf "%08d %s %04X\n",a,$1,a}' build/kea48.sym | sort -n | awk 'NR>1 && $1-prev>=24 {printf "   gap %5d B before %s\n",$1-prev,$2} {prev=$1}' | head -40
echo "--- is anything above 0xFF00 used?"
grep -nE '65281|0xFF01|65535|0xFFFF|UDG|65368' src/48k/kea48.asm src/common/*.asm tools/gen48.py tools/mktap48.py | head
echo "--- ISR (depth)"
sed -n "$(grep -n '^isr:' src/48k/kea48.asm | cut -d: -f1),+25p" src/48k/kea48.asm | head -40
echo "--- in_read full"
sed -n 22,75p src/common/input.asm
echo "--- game_a rest + strafe?"
sed -n 40,80p src/common/game_a.asm
grep -nE 'bit 6|bit 7|strafe' src/common/game_a.asm src/48k/kea48.asm | head
echo "--- main loop: pause / in_break use"
grep -nE 'in_break|fe_pause' src/48k/kea48.asm src/common/game*.asm | head
echo "--- make128 mechanics"
sed -n 1,30p tools/make128.py | grep -vE '^\s*$' | head -30
echo "--- how tests fire / which keys"
grep -nE 'fire|"M"|SPACE|keys\(' tools/test_game_hud.py tools/test_game_enemies.py tools/test_game_doors.py tools/test_game_sprites.py tools/t6_playthrough.py tools/m22_shots.py | head -20
echo "--- print routine users"
grep -nE 'call print\b|jp print\b' src/48k/kea48.asm src/common/*.asm | head
