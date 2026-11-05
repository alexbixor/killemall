#!/bin/bash
# m23_survey2.sh - READ-ONLY: where is free RAM/tape room for M2.3 (floor lines)? low block layout, ORG/CLEAR derivation, frames use
cd ~/work/killemall
S=build/kea48.sym
echo "--- symbols 0x5B00..0x8100 (addr label gap-to-next)"
grep -E 'EQU 0[0-9A-F]{4}H' $S | awk '{gsub("H","",$3); gsub("^0","",$3); printf "%s %s\n", $3, $1}' | sort | awk 'BEGIN{p=0;pl=""} {a=strtonum("0x"$1); if(pl!="" && p>=0x5B00 && p<0x8100) printf "  %04X %-14s %5d\n", p, pl, a-p; p=a; pl=$2}' | head -60
echo "--- ORG / CLEAR / p1 derivation"
grep -n -iE 'org|CLEAR|27903|27904|0x6D00|6D00' src/48k/kea48.asm tools/mktap48.py tools/make128.py tools/mktap128.py tools/stage128.py tools/build128.sh 2>/dev/null | head -20
echo "--- frames usage"
grep -rn 'frames' src/common/*.asm src/48k/kea48.asm | grep -v '^.*;.*frames' | head -10
echo "--- cls usage"; grep -rn -E 'call cls|jp cls' src/common/*.asm src/48k/kea48.asm | head
echo "--- 0x6AE0 / 0x6B00 users"; grep -rn -iE '0x6AE0|0x6B00|0x6C00|27360|27392|27648' src/common/*.asm src/48k/kea48.asm tools/*.py | head -10
echo "--- what tests poke at 0x6AE0"; grep -n '0x6AE0' tools/test_game_enemies.py | head -3
echo "--- game_a.asm full"; cat src/common/game_a.asm
echo "--- test_128 build steps"; sed -n 1,25p tools/test_128.py | grep -n -iE 'build|make128|subprocess|tap' | head