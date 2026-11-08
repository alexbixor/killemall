#!/bin/bash
# build_m24_48.sh - M2.4 (sprite card: no colour bleeding + zombie art): same steps as build_m23_48.sh, output
# build/killemall48_m24.tap. m2 / m22 / m23 tapes stay untouched (m23 sha 58821537).
set -e
cd ~/work/killemall
export KEA_CLIPSET=${KEA_CLIPSET:-104,112,128}
.venv/bin/python tools/spritec.py assets/sprites src/gen/sprites_data.asm build/m24_sheet.png
python3 tools/gen48.py
python3 tools/mapc.py 48k src/48k/gen/level48.bin assets/levels/01_entry.txt
python3 tools/mapc.py 48k build/level48_02.bin assets/levels/02_barracks.txt
python3 tools/mapc.py 48k build/level48_03.bin assets/levels/03_furnace.txt
python3 tools/mklevelblk.py build/level48_02.bin 2 build/level48_02.blk
python3 tools/mklevelblk.py build/level48_03.bin 3 build/level48_03.blk
python3 tools/mklevelblk.py src/48k/gen/level48.bin 1 src/48k/gen/level48.bin
cd src/48k && pasmo --tapbas kea48.asm ../../build/kea48.tap ../../build/kea48.sym && cd ../..
ls -la build/kea48.tap | awk '{print "tap bytes", $5}'
python3 tools/mktap48.py build/kea48.tap build/title.scr build/killemall48_m24.tap --raw build/level48_02.blk build/level48_03.blk src/48k/gen/level48.bin
python3 tools/tapdump.py build/killemall48_m24.tap
grep -E "^(hi_end|start|fe_run|in_read|snd_fx|mt_outer|game_tick|hud_init|level_data|BANDTAB|TEX|SCHAIN_END|HTABN|fl_set|fl_end|RECIP|ds_cols|dc_attr|spr_table|SCHAIN)\s" build/kea48.sym | tr '\n' ' '; echo
awk '$1=="HTABN"{h=$3} $1=="fl_end"{e=$3} END{ if (h=="0D800H") print "HTABN at 0xD800: floor.asm inside the padding, fl_end " e; else { print "HTABN MOVED to " h " - floor.asm overflowed the padding"; exit 1 } }' build/kea48.sym
awk '$1=="hi_end"{a=$3; sub(/H$/,"",a); v=strtonum("0x" a); printf "hi_end 0x%04X gap to stack top 0xFDF0: %d B (stack uses 18 B)\n", v, 65008-v; if (65008-v < 40) { print "HIGH BLOCK TOO CLOSE TO THE STACK"; exit 1 } }' build/kea48.sym
awk '$1=="level_data"{a=$3; sub(/H$/,"",a); v=strtonum("0x" a); printf "level_data 0x%04X + 1081 = 0x%04X, free below 0x8000: %d B\n", v, v+1081, 32768-(v+1081); if (32768-(v+1081) < 0) { print "LOW BLOCK OVERFLOWS 0x8000"; exit 1 } }' build/kea48.sym
cmp build/killemall48_m2.tap build/killemall48_m2_orig.tap && echo "m2 tape pristine: yes"
sha256sum build/killemall48_m22.tap | grep -q '^672bfe8cb89e84a7' && echo "m22 tape pristine: yes"
sha256sum build/killemall48_m23.tap | grep -q '^58821537' && echo "m23 tape pristine: yes"
