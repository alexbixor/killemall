#!/bin/bash
# build128_hires.sh - lane S (6 Nov 2026): Kill'em all 128K HIRES spike build (pasmo --equ HIRES=1 on top of the default
# GLIDE/MOUSE/FLIP flags). Writes build/kea128_hires.tap/.sym, build/bank3.bin, build/killemall128_hires.tap. The default
# build (tools/build128.sh -> build/kea128.tap, build/killemall128_m2.tap) is NOT touched: byte-identical by construction
# (the only shared outputs rewritten here are build/bank1.bin and src/128k/kea128_gen.asm, both deterministic from the same sources).
# lane K1 (6 Nov 2026): --equ LEVELS8=1 (8 levels, 36 things, real enemy rows) on every 128K build; the low code block
# (lowcode.asm + hr_pass) is assembled standalone at LOWCODE 5BC0h by tools/lev128.py --hires and travels in bank 1.
set -e
cd ~/work/killemall
SRC=${1:-src/48k/kea48.asm}
.venv/bin/python tools/lev128.py --hires
.venv/bin/python tools/gen_hires.py
.venv/bin/python tools/make128.py "$SRC" src/128k/kea128_gen.asm
( cd src/48k && pasmo --equ GLIDE=1 --equ MOUSE=1 --equ FLIP=1 --equ LEVELS8=1 --equ HIRES=1 --tap ../128k/kea128_gen.asm ../../build/kea128_hires.tap ../../build/kea128_hires.sym )
.venv/bin/python tools/lev128.py --hires --fix build/kea128_hires.sym   # pass 2: hr_pass with the engine's fl_wait/BANKM/fl_pg0/draw_sprite
( cd src/128k && pasmo --equ LEVELS8=1 --equ HIRES=1 --bin bank1.asm ../../build/bank1.bin ../../build/bank1.sym )
# bank 3 needs the fixed-area addresses of this image: isr, zbuf, BUF, CHJ, spr_table, dc_white, dc_mark, dc_wlo, ds_ink, dc_bcol
EQUS=$(.venv/bin/python tools/sym_equs.py build/kea128_hires.sym isr zbuf BUF CHJ spr_table dc_white dc_mark dc_wlo ds_ink dc_bcol)
( cd src/128k && pasmo $EQUS --bin bank3.asm ../../build/bank3.bin ../../build/bank3.sym )
.venv/bin/python tools/mktap128.py build/kea128_hires.tap build/bank1.bin build/title.scr build/killemall128_hires.tap build/bank3.bin@61440
ls -la build/bank3.bin build/kea128_hires.tap build/killemall128_hires.tap | awk '{print $9, $5}'
awk '$1=="hi_end"{a=$3; sub(/H$/,"",a); v=strtonum("0x" a); printf "HIRES hi_end 0x%04X gap to stack top 0xFDF0: %d B\n", v, 65008-v; if (65008-v < 40) { print "128K HIGH BLOCK TOO CLOSE TO THE STACK"; exit 1 } }' build/kea128_hires.sym
awk '$1=="low_end"{a=$3; sub(/H$/,"",a); v=strtonum("0x" a); printf "HIRES low_end 0x%04X free below 0x8000: %d B\n", v, 32768-v; if (32768-v < 0) { print "LOW BLOCK OVERFLOWS 0x8000"; exit 1 } }' build/kea128_hires.sym
awk '$1=="hires_end"{a=$3; sub(/H$/,"",a); v=strtonum("0x" a); printf "bank 3 used F000h..0x%04X = %d B (+260 B IM2 mirror at FDFDh)\n", v, v-61440; if (v > 65021) { print "BANK 3 OVERLAPS THE IM2 MIRROR"; exit 1 } }' build/bank3.sym
awk '$1=="bank1_end"{a=$3; sub(/H$/,"",a); v=strtonum("0x" a); printf "bank 1 used C000h..0x%04X = %d B (free %d B)\n", v, v-49152, 65536-v; if (v > 65536) { print "BANK 1 OVERFLOWS 16K"; exit 1 } }' build/bank1.sym
