#!/bin/bash
# m23_survey3.sh - READ-ONLY: tail of kea48, height tables, geo48 flow, bump_action/strafe, recorder tools, 128 build
cd ~/work/killemall
echo "--- kea48 tail 940..949"; sed -n 940,949p src/48k/kea48.asm
echo "--- gen48 heights 41..57"; sed -n 41,57p tools/gen48.py
echo "--- geo48.sh"; cat tools/geo48.sh
echo "--- chk48 main"; sed -n 60,80p tools/chk48.py
echo "--- strafe anywhere in game_*/sprites_*"; grep -n -iE 'strafe|bit 6,a|bit 7,a' src/common/game_*.asm src/common/hud*.asm | head
echo "--- bump_action head"; grep -n -A8 '^bump_action:' src/common/game_b.asm | head -12
echo "--- recorders"; ls tools/ | grep -iE 'play|demo|video|rec|gif' ; grep -ln 'mp4' tools/*.py | head
echo "--- build128 + test_128 heads"; sed -n 1,20p tools/build128.sh; grep -n -iE 'subprocess|build128|make128|def test|check\(' tools/test_128.py | head -20
echo "--- make128 anchors"; grep -n -iE 'A1|A2|A3|A4|A5|re\.|anchor' tools/make128.py | head -30
echo "--- render: who calls CLRBUF / after"; sed -n 411,440p src/48k/kea48.asm
echo "--- opt_detail apply"; sed -n 85,96p src/48k/kea48.asm
echo "--- status file size"; wc -l build/m22_status.txt