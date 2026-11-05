#!/bin/bash
# m25_survey1.sh - read-only survey of window geometry constants, HUD rows, clear/copy, ceiling attr
cd ~/work/killemall || exit 1
echo "== files"; wc -l src/48k/kea48.asm src/common/*.asm tools/gen48.py | tail -25
echo "== window/BUF constants (kea48.asm)"
grep -nE "BUF|CLRBUF|COPYBUF|ATTRBUF|ATTRCOPY|WIN_|NROWS|NCOLS|96|128|0x6000|24576|27168|zbuf|HORIZ" src/48k/kea48.asm | head -80
echo "== gen48.py geometry params"
grep -nE "^[A-Z_]+ *= *[0-9]|def gen_|BANDTAB|CLIPSET|CLRBUF|COPYBUF|ROWTAB|HTABN|HTABF|HORIZ|FOV|NRAY|RAYS|ROWS|FLOOR|CEIL" tools/gen48.py | head -80
echo "== ceiling / floor attr"
grep -nE -i "ceil|floor_attr|fl_attr|attr_c|attr_f|paper|ink" src/48k/kea48.asm | head -40
echo "== HUD rows"
grep -nE -i "row|line|0x5[0-9A-F]{3}|2[0-9]{4}" src/common/hud*.asm | grep -iE "equ|row" | head -60
echo "== prof tool?"; ls tools | grep -iE "prof|fps|m23_fps|t6_" 