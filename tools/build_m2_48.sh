#!/bin/bash
# build_m2_48.sh - T6: assemble the integrated 48K edition (tools/build48.sh steps with the gen48 band knob) and build the
# final tape build/killemall48_m2.tap = BASIC autostart + title SCREEN$ + code + levels 02/03 as headerless blocks.
# env: KEA_CLIPSET (default "104,112,128": BANDC_160/192 dropped to make room for T2+T3; see build/m2_report.md)
set -e
cd ~/work/killemall
export KEA_CLIPSET=${KEA_CLIPSET:-104,112,128}
python3 tools/gen48.py
python3 tools/mapc.py 48k src/48k/gen/level48.bin assets/levels/01_entry.txt
python3 tools/mapc.py 48k build/level48_02.bin assets/levels/02_barracks.txt
python3 tools/mapc.py 48k build/level48_03.bin assets/levels/03_furnace.txt
# raw tape blocks for load_level: id byte + level body padded to 1081 B (tools/mklevelblk.py); level 1 gets the same layout
python3 tools/mklevelblk.py build/level48_02.bin 2 build/level48_02.blk
python3 tools/mklevelblk.py build/level48_03.bin 3 build/level48_03.blk
python3 tools/mklevelblk.py src/48k/gen/level48.bin 1 src/48k/gen/level48.bin
cd src/48k && pasmo --tapbas kea48.asm ../../build/kea48.tap ../../build/kea48.sym && cd ../..
ls -la build/kea48.tap | awk '{print "tap bytes", $5}'
# level blocks in play order: 2, 3, then 1 again (START after the end of level 3 / QUIT re-fetches level 1 from tape)
python3 tools/mktap48.py build/kea48.tap build/title.scr build/killemall48_m2.tap --raw build/level48_02.blk build/level48_03.blk src/48k/gen/level48.bin
python3 tools/tapdump.py build/killemall48_m2.tap
grep -E "^(hi_end|start|fe_run|in_read|snd_fx|mt_outer|game_tick|hud_init|level_data|BANDTAB|TEX)\s" build/kea48.sym | tr '\n' ' '; echo
