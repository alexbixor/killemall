#!/bin/bash
# m22_survey2.sh - read-only greps for the dashboard implementation (kept in a file: long inline commands get blocked)
cd ~/work/killemall
echo "== frontend print usage"; grep -n "print\|fe_clr_bottom:" src/common/frontend.asm | head -12
echo "== fe_clr_bottom body"; awk '/^fe_clr_bottom:/{f=1} f{print; n++} n>22{exit}' src/common/frontend.asm
echo "== test_frontend counts"; grep -n "7\b\|8\b\|count\|items" tools/test_frontend.py | head -20
echo "== ammo cap / keys bits"; grep -n "ammo\|keys" src/common/game_c.asm | head -20
echo "== bright / 64 in attrs"; grep -n "or 64\|add a,64\|0x40\|TYPEINK\|CODEINK\|ATTRTAB" src/common/sprites*.asm src/48k/kea48.asm tools/gen48.py | head -20
echo "== sprite size (hv)"; grep -n "muls_7\|mul16\|16/24\|\*16\|hv" src/common/sprites.asm src/common/sprites_b.asm src/common/sprites_c.asm | head -30
echo "== far wall / hit_far"; grep -n "hit_far\|far" src/48k/kea48.asm src/48k/gen/dda48.asm tools/gen48.py | head -20
echo "== sprites48 gen + low block"; grep -n "sprites48\|27904\|spare\|org " tools/*.py tools/*.sh 2>/dev/null | grep -v "^tools/make128\|Binary" | head -12
echo "== low block end"; grep -E "^(level_data|SPG|SCHAIN_END|spr_table|NCTAB|STEPTAB|VSTEP)\s" build/kea48.sym
echo "== stack use: deepest call chain guess - count 'call' in render path irrelevant; show TABLE/ISRVEC"; grep -n "TABLE\|ISRVEC\|ld sp" src/48k/kea48.asm | head
