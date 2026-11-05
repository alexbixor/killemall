#!/bin/bash
# Kill'em all M2: verify deliverables + copy both tapes to the Deck (read-only otherwise)
cd /home/ubuntu/work/killemall
OUT=build/deck_copy_m2.out
{
date -u +%H:%M:%SZ
ls -la --time-style=+%H:%M build/killemall48_m2.tap build/killemall128_m2.tap build/m2_title.png build/m2_menu.png build/m2_game.png build/m2_demo.mp4 build/kea128_title.png build/kea128_menu.png build/kea128_game.png build/m2_report.md build/t4_report.md 2>&1 | cut -c28-
md5sum build/killemall48_m2.tap build/killemall128_m2.tap
echo "--- t4 report (fps/AY lines)"
grep -iE 'fps|AY|torn|not done' build/t4_report.md | cut -c1-220
echo "--- deck"
ssh -o ConnectTimeout=8 -o BatchMode=yes ${DECK:?set DECK=user@host} 'pgrep -f "[r]eaper SteamLaunch" >/dev/null && echo PLAYING || echo idle'
scp -o ConnectTimeout=8 -o BatchMode=yes build/killemall48_m2.tap build/killemall128_m2.tap ${DECK:?set DECK=user@host}:~/Emulation/roms/zxspectrum/ && echo scp_ok
ssh -o ConnectTimeout=8 -o BatchMode=yes ${DECK:?set DECK=user@host} 'md5sum ~/Emulation/roms/zxspectrum/killemall48_m2.tap ~/Emulation/roms/zxspectrum/killemall128_m2.tap; ls ~/Emulation/roms/zxspectrum/'
} > $OUT 2>&1
cat $OUT
