#!/bin/bash
# m24_gates.sh - M2.4 full verification: lane tests + geo48 (t6_gates), sprite card, floor lines, sprite scale, stack depth,
# 128K, pristine tapes. Run AFTER tools/build_m24_48.sh (build/kea48.tap == the m24 build).
cd ~/work/killemall
bash tools/build_m24_48.sh > build/m24_build.out 2>&1; echo "build exit $? : $(grep -E 'hi_end 0x' build/m24_build.out)"  | tee build/m24_gates.out
bash tools/t6_gates.sh 2>&1 | tee -a build/m24_gates.out
for t in test_sprite_card test_floor_lines test_sprite_scale test_128; do
  timeout 550 .venv/bin/python tools/$t.py > build/m24_$t.out 2>&1; echo "$t exit $? : $(tail -1 build/m24_$t.out | cut -c1-90)"
done | tee -a build/m24_gates.out
timeout 300 .venv/bin/python tools/m22_stack.py > build/m24_stack.out 2>&1; echo "m22_stack exit $? : $(grep -E 'deepest|gap' build/m24_stack.out | head -1)" | tee -a build/m24_gates.out
grep -E '^(hi_end|level_data|spr_table)\s' build/kea48.sym | tee -a build/m24_gates.out
sha256sum build/killemall48_m24.tap build/killemall48_m23.tap build/killemall48_m22.tap | cut -c1-16,66- | tee -a build/m24_gates.out
ls -l build/killemall48_m24.tap | awk '{print "m24 tape", $5, "B"}' | tee -a build/m24_gates.out
