#!/bin/bash
# build_m23_48.sh - M2.3 (floor lines + SPACE fire): same steps as build_m22_48.sh, output build/killemall48_m23.tap.
# build/killemall48_m22.tap (M2.2, sha 672bfe8c) and build/killemall48_m2.tap (M2.1) stay untouched.
# Extra check: floor.asm must sit inside the alignment padding before HTABN (HTABN stays at 0xD800 -> 0 B of code budget used).
set -e
cd ~/work/killemall
export KEA_CLIPSET=${KEA_CLIPSET:-104,112,128}
python3 tools/gen48.py
python3 tools/mapc.py 48k src/48k/gen/level48.bin assets/levels/01_entry.txt
python3 tools/mapc.py 48k build/level48_02.bin assets/levels/02_barracks.txt
python3 tools/mapc.py 48k build/level48_03.bin assets/levels/03_furnace.txt
python3 tools/mklevelblk.py build/level48_02.bin 2 build/level48_02.blk
python3 tools/mklevelblk.py build/level48_03.bin 3 build/level48_03.blk
python3 tools/mklevelblk.py src/48k/gen/level48.bin 1 src/48k/gen/level48.bin
cd src/48k && pasmo --tapbas kea48.asm ../../build/kea48.tap ../../build/kea48.sym && cd ../..
ls -la build/kea48.tap | awk '{print "tap bytes", $5}'
python3 tools/mktap48.py build/kea48.tap build/title.scr build/killemall48_m23.tap --raw build/level48_02.blk build/level48_03.blk src/48k/gen/level48.bin
python3 tools/tapdump.py build/killemall48_m23.tap
grep -E "^(hi_end|start|fe_run|in_read|snd_fx|mt_outer|game_tick|hud_init|level_data|BANDTAB|TEX|SCHAIN_END|HTABN|fl_set|fl_end|RECIP)\s" build/kea48.sym | tr '\n' ' '; echo
awk '$1=="HTABN"{h=$3} $1=="fl_end"{e=$3} END{ if (h=="0D800H") print "HTABN at 0xD800: floor.asm inside the padding, fl_end " e; else { print "HTABN MOVED to " h " - floor.asm overflowed the padding"; exit 1 } }' build/kea48.sym
cmp build/killemall48_m2.tap build/killemall48_m2_orig.tap && echo "m2 tape pristine: yes"
sha256sum build/killemall48_m22.tap | grep -q '^672bfe8cb89e84a7' && echo "m22 tape pristine: yes"