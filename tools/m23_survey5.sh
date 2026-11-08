#!/bin/bash
# m23_survey5.sh - READ-ONLY: last facts before editing (gates list, pause menu items, pad test e2e, launcher, demo tool, ffmpeg)
cd ~/work/killemall
echo "--- t6_gates.sh"; cat tools/t6_gates.sh
echo "--- pause menu items / redefine entry"; grep -n -iE 'RESUME|QUIT|fe_pause:|fe_redef:|PAUSED|pause' src/common/frontend.asm | head -12
echo "--- pad test 126..175"; sed -n 126,175p tools/m22_pad_test.py
echo "--- launcher 20..34"; sed -n 20,34p tools/deck/launch-killemall.sh
echo "--- t6_demo head"; sed -n 1,12p tools/t6_demo.py
echo "--- ffmpeg"; command -v ffmpeg && ffmpeg -version | head -1
echo "--- chk48 head 1..43"; sed -n 1,43p tools/chk48.py
echo "--- tests touching M key / in_keys"; grep -rn -E 'tap\("M"\)|press\("M"|"M"\]|in_keys' tools/test_*.py | head
echo "--- BUF rows 96..127 users?"; grep -rn -iE 'BUF\+96|BUF \+ 96|\+96\b.*BUF|0x6060|0x60E0' src/common/*.asm src/48k/kea48.asm tools/gen48.py | head -5
echo "--- walk/ph_step name clash?"; grep -rn -wE 'walk|ph_step|FLOORL|fl_n|fl_c|mb_adv' src/ tools/gen48.py | head -5