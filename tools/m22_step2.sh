#!/bin/bash
# m22_step2.sh - verify the DRAM relocation: show state.asm, ROWTAB/ds_rmin addressing, layout symbols; build; measure
cd ~/work/killemall
echo "== state.asm"; cat src/common/state.asm
echo "== ROWTAB / ds_rmin / things / vis / zbuf / door_log / fe_tmpk addressing (page assumptions?)"
grep -n "ROWTAB\|ds_rmin\|ds_rmax" src/common/*.asm src/48k/kea48.asm | grep -v "^src/common/state.asm" | head -20
echo "== layout symbols (pre vs now)"
for s in TABLE lo_start lo_end hi_start hi_end ISRVEC DRAM DRAM_END things vis zbuf door_log fe_tmpk ROWTAB ds_rmin ds_rmax ATTRBUF FTY; do
  printf "%-10s pre=%-6s now=%s\n" "$s" "$(grep -E "^$s\s" build/pre_m22/kea48_pre_m22.sym | awk '{print $3}')" "$(grep -E "^$s\s" build/kea48.sym | awk '{print $3}')"
done
echo "== org / loader / tap layout"
grep -n "org\|ORG" src/48k/kea48.asm | head -5
grep -n "CLEAR\|USR\|org\|0x5\|23" tools/mktap48.py | head -12
echo "== build"
bash tools/build_m22_48.sh > build/m22_build2.log 2>&1; echo "build exit=$?"; grep -i "error\|warning" build/m22_build2.log | head; tail -4 build/m22_build2.log
echo "== after build"
for s in hi_end DRAM DRAM_END things ds_rmin ds_rmax ROWTAB lo_end; do printf "%-10s now=%s\n" "$s" "$(grep -E "^$s\s" build/kea48.sym | awk '{print $3}')"; done
ls -l build/killemall48_m22.tap; cmp build/killemall48_m2.tap build/killemall48_m2_orig.tap && echo M2_TAP_PRISTINE
