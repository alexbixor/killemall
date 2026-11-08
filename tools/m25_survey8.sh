#!/bin/bash
# m25_survey8.sh - read-only: window-dependent constants outside the renderer, harness page users, tape layout, pixdata gen
cd ~/work/killemall || exit 1
echo "== game/frontend/hud refs to window cols/addresses"
grep -nE "ATTRWIN|22568|BUF\b|BUF\+|0x4[0-9A-F]{3}|0x5[0-7][0-9A-F]{2}|1[6-9][0-9]{3}\b|2[0-3][0-9]{3}\b" src/common/game_*.asm src/common/frontend.asm src/common/sprites*.asm src/common/input.asm src/common/beeper.asm src/common/stubs.asm | grep -vE "^\S+:\s*;" | head -40
echo "== harness page / window constants in tools"
grep -nE "0x6A|6A00|6AF0|27136|27376|0x6a" tools/*.py tools/*.sh | head -40
echo "== tools using 64 + 2 \* r or x = 64 / crop 192"
grep -nE "64 \+ 2|2 \* r|\(192, ?24|range\(8, ?24\)|8 \+ bx|bx in range|\* 2 \+ 64|x0 = 64|cols? 8" tools/*.py | head -40
echo "== mktap48 / tapdump"
sed -n 1,40p tools/mktap48.py
echo "== m24 build out (tape structure)"
grep -A14 -E "tapdump|block" build/m24_build.out | head -40
echo "== m22_pixdata.py exists?"; ls -la tools/m22_pixdata.py 2>/dev/null && grep -nE "18183|18184|18200|22535|def |frame|7, |63|192" tools/m22_pixdata.py | head -30
echo "== load_level / level_data users"
grep -nE "level_data|load_level|1081|1242" src/48k/kea48.asm src/common/*.asm tools/make128.py tools/mktap48.py tools/mklevelblk.py 2>/dev/null | grep -vE "^\S+:\s*;" | head -30
echo "== test tools list + sizes"
wc -l tools/test_*.py tools/t6_*.py tools/t6_*.sh tools/m24_shots.py tools/m22_stack.py tools/prof48.py 2>/dev/null
echo "== apply_opts / cl_de users"
grep -nE "cl_de|cl_fl|cl_sp|cl_col|opt_detail" src/48k/kea48.asm src/common/*.asm | grep -vE "^\S+:\s*;"
