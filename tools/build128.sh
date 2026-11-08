#!/bin/bash
# build128.sh - Kill'em all 128K edition (lane T4): levels -> bank1.bin, make128 -> kea128_gen.asm -> code block, tape.
# usage: tools/build128.sh [kea48.asm]   (default src/48k/kea48.asm; the engine image is assembled from the transformed source)
# lane K1 (6 Nov 2026): pasmo --equ LEVELS8=1 = 8 levels / 36 things / real enemy rows (shim128.asm, state.asm, etab.asm,
# bank1.asm, lowcode128.asm); the 48K build (tools/build_m25_48.sh, tools/gates_v1.sh) never sees the symbol.
# lane M2 (7 Nov 2026): pasmo --equ BANK3=1 = the bank-3 hi-res blitter (src/128k/bank3.asm) draws enemy types 3..6 from their
# own 32x48 art on the DEFAULT tape too: the low code block carries hr_pass (lev128.py --bank3), bank3.asm is assembled with the
# engine's fixed-area addresses (tools/sym_equs.py) and travels on the tape as a second bank image (mktap128 bank3.bin@<bank3_org>).
# Zombies keep the old 3-px path on this tape (HIRES is not defined); tools/build128_hires.sh is the hi-res zombie build.
set -e
cd "$(dirname "$0")/.."   # repo root
SRC=${1:-src/48k/kea48.asm}
.venv/bin/python tools/lev128.py --bank3             # lev128_{0..7}.bin, lowcode128.bin/.sym (with hr_pass), gen/lev128_sizes.asm, gen/lowcode128_equ.asm
.venv/bin/python tools/gen_hires.py                  # gen/hires_art.asm (zombie frames, HIRES build), gen/hires_art2.asm (types 3..6), gen/hires_tabs.asm
.venv/bin/python tools/make128.py "$SRC" src/128k/kea128_gen.asm
# --tap: pasmo writes a CODE header whose start = lowest org (27904) -> mktap128 takes code + start from it
( cd src/48k && pasmo --equ GLIDE=1 --equ MOUSE=1 --equ FLIP=1 --equ LEVELS8=1 --equ BANK3=1 --tap ../128k/kea128_gen.asm ../../build/kea128.tap ../../build/kea128.sym )   # M2.9b: camera glide (128K/Next only); lane M: mouse look (128K/Next only)
# lane F (6 Nov 2026): --equ FLIP=1 = shadow-screen flip (shim128.asm / flip_hi.asm); drop it for the single-screen build (byte-identical to pre-F).
.venv/bin/python tools/lev128.py --bank3 --fix build/kea128.sym   # pass 2: the low code block with the engine's addresses (layout asserted unchanged)
( cd src/128k && pasmo --equ LEVELS8=1 --bin bank1.asm ../../build/bank1.bin ../../build/bank1.sym )
# bank 3 needs the fixed-area addresses of this image: isr, zbuf, BUF, CHJ, spr_table, dc_white, dc_mark, dc_wlo, ds_ink, dc_bcol, things
EQUS=$(.venv/bin/python tools/sym_equs.py build/kea128.sym isr zbuf BUF CHJ spr_table dc_white dc_mark dc_wlo ds_ink dc_bcol things)
( cd src/128k && pasmo $EQUS --bin bank3.asm ../../build/bank3.bin ../../build/bank3.sym )
B3ORG=$(awk '$1=="bank3_org"{a=$3; sub(/H$/,"",a); print strtonum("0x" a)}' build/bank3.sym)
.venv/bin/python tools/mktap128.py build/kea128.tap build/bank1.bin build/title.scr build/killemall128_m2.tap build/bank3.bin@$B3ORG
ls -la build/bank1.bin build/bank3.bin build/kea128.tap build/killemall128_m2.tap | awk '{print $9, $5}'
# 1 Nov: layout gates on the 128K symbol file too (the right 7 byte columns vanished when COLBASE crossed a page in THIS image only)
awk '$1=="COLBASE"{a=$3; sub(/H$/,"",a); v=strtonum("0x" a)} $1=="HTABN"{h=$3; sub(/H$/,"",h); hv=strtonum("0x" h)} END{ printf "128K COLBASE 0x%04X..0x%04X page-contained below HTABN: %s\n", v, v+47, (int(v/256)==int((v+47)/256) && v+48<=hv)?"yes":"NO"; if (int(v/256)!=int((v+47)/256) || v+48>hv) exit 1 }' build/kea128.sym
awk '$1=="BANDTAB"{a=$3; sub(/H$/,"",a); v=strtonum("0x" a)} $1=="dsp_tab"{d=$3; sub(/H$/,"",d); dv=strtonum("0x" d)} END{ printf "128K BANDTAB 0x%04X page aligned: %s, BANDTAB..dsp_tab+8 in one page: %s\n", v, (v%256==0)?"yes":"NO", (int(v/256)==int((dv+7)/256))?"yes":"NO"; if (v%256!=0 || int(v/256)!=int((dv+7)/256)) exit 1 }' build/kea128.sym
awk '$1=="hi_end"{a=$3; sub(/H$/,"",a); v=strtonum("0x" a); printf "128K hi_end 0x%04X gap to stack top 0xFDF0: %d B\n", v, 65008-v; if (65008-v < 40) { print "128K HIGH BLOCK TOO CLOSE TO THE STACK"; exit 1 } }' build/kea128.sym
awk '$1=="low_end"{a=$3; sub(/H$/,"",a); v=strtonum("0x" a); printf "128K low_end 0x%04X free below 0x8000: %d B\n", v, 32768-v; if (32768-v < 0) { print "LOW BLOCK OVERFLOWS 0x8000"; exit 1 } }' build/kea128.sym
awk '$1=="bank1_end"{a=$3; sub(/H$/,"",a); v=strtonum("0x" a); printf "bank 1 used C000h..0x%04X = %d B (free %d B)\n", v, v-49152, 65536-v; if (v > 65536) { print "BANK 1 OVERFLOWS 16K"; exit 1 } }' build/bank1.sym
# lane M2 bank-3 gates: art2_end <= F000h (hr_entry MUST stay at F000h: lowcode.asm hr_pass does `call 0F000h`), hr_code_end <= F300h (HRBLO),
# hires_end <= FDFDh (IM2 mirror); the low code block (hr_pass included) ends <= 5C43h (tools/test_k1.py asserts the same)
awk '$1=="bank3_org"{a=$3; sub(/H$/,"",a); o=strtonum("0x" a)} $1=="art2_end"{a=$3; sub(/H$/,"",a); v=strtonum("0x" a)} $1=="hr_entry"{a=$3; sub(/H$/,"",a); e=strtonum("0x" a)} $1=="hr_code_end"{a=$3; sub(/H$/,"",a); c=strtonum("0x" a)} $1=="hires_end"{a=$3; sub(/H$/,"",a); h=strtonum("0x" a)} END{ printf "bank 3: art2 0x%04X..0x%04X = %d B (free below F000h %d B), hr_entry 0x%04X, code end 0x%04X (free below F300h %d B), hires_end 0x%04X (free below FDFDh %d B)\n", o, v, v-o, 61440-v, e, c, 62208-c, h, 65021-h; if (v > 61440 || e != 61440 || c > 62208 || h > 65021) { print "BANK 3 LAYOUT GATE FAILED"; exit 1 } }' build/bank3.sym
awk '$1=="low_end"{a=$3; sub(/H$/,"",a); v=strtonum("0x" a); printf "low code block ends 0x%04X (stack bound 0x5C43, %d B spare)\n", v, 23619-v; if (v > 23619) { print "LOW CODE BLOCK OVERLAPS THE STACK"; exit 1 } }' build/lowcode128.sym
