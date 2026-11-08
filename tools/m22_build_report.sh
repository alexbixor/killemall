#!/bin/bash
# m22_build_report.sh - build the M2.2 tape and report errors + key symbols (kept in a file: inline chains get blocked)
cd ~/work/killemall
bash tools/build_m22_48.sh > build/m22_build_last.log 2>&1; echo "build exit=$?"
grep -i "error\|warning\|undefined\|duplicate" build/m22_build_last.log | head
tail -3 build/m22_build_last.log
for s in hi_end hud_init hud_update DASH_RUNS DASH_LABELS PILLS SCHAIN_END level_data; do
  printf "%-12s %s\n" $s "$(grep -E "^$s\s" build/kea48.sym | awk '{print $3}')"
done
python3 -c "
import re
syms={}
for l in open('build/kea48.sym'):
    m=re.match(r'(\S+)\s+EQU\s+([0-9A-F]+)H',l)
    if m: syms[m.group(1)]=int(m.group(2),16)
if 'hi_end' in syms: print('free high block: 65008-16 ... hi_end -> %d B (stack top 65008, keep >= ~60 B for the stack)' % (65008-syms['hi_end']))
if 'level_data' in syms: print('low block free below 32768: %d B' % (32768-(syms['level_data']+1081)))
"
ls -l build/killemall48_m22.tap 2>/dev/null
cmp build/killemall48_m2.tap build/killemall48_m2_orig.tap && echo M2_TAP_PRISTINE
