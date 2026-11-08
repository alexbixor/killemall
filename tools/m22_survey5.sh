#!/bin/bash
# m22_survey5.sh - read-only checks before relocating RAM tables and editing sprites
cd ~/work/killemall
echo "== NTHINGS VISMAX"; grep -n "NTHINGS\s*equ\|VISMAX\s*equ" src/common/*.asm
echo "== page arithmetic on relocatable labels"; grep -n "things and\|things/256\|vis and\|vis/256\|zbuf and\|zbuf/256\|door_log and\|fe_tmpk and\|ds_rmin and\|ds_rmin/256\|high things\|high vis\|high zbuf" src/common/*.asm src/48k/kea48.asm
echo "== all refs to zbuf"; grep -n "zbuf" src/common/*.asm src/48k/kea48.asm | grep -v "^src/common/stubs"
echo "== all refs to vis (word)"; grep -nw "vis" src/common/*.asm src/48k/kea48.asm | grep -v "^src/common/stubs"
echo "== door_log / fe_tmpk refs"; grep -n "door_log\|fe_tmpk" src/common/*.asm | grep -v "^src/common/stubs"
echo "== frames in tools"; grep -ln "\"frames\"\|'frames'" tools/*.py
echo "== make128 anchors"; grep -n "re\.\(match\|search\|sub\)\|anchor\|A[1-5]" tools/make128.py | head -30
echo "== 128 rom all-FF pages (ROM1 = second 16K)"; ls tools/zesarux/*.rom; python3 -c "
import glob
for f in glob.glob('tools/zesarux/*.rom'):
    r=open(f,'rb').read(); print(f, len(r))
    for base in range(0,len(r),16384):
        rom=r[base:base+16384]
        print('  rom', base//16384, 'FF pages:', [hex(p) for p in range(64) if rom[p*256:(p+1)*256]==b'\xff'*256])"
echo "== type field of things / hitscan use of vis"; sed -n 1,12p src/common/sprites.asm; grep -n "vis\|tnc\|tc0\|NCTAB" src/common/game_g.asm | head
echo "== thing_xform2 caller + type"; grep -n "thing_xform2\|ld a,(ix+0)\|and 31" src/common/sprites_b.asm src/common/sprites_c.asm src/common/sprites_d.asm | head
