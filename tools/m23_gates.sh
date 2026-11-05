#!/bin/bash
# m23_gates.sh - M2.3 full verification: lane tests + geo48 (t6_gates), floor lines, sprite scale, stack depth, 128K, pristine tapes
cd ~/work/killemall
bash tools/t6_gates.sh 2>&1 | tee build/m23_gates.out
for t in test_floor_lines test_sprite_scale test_128; do
  timeout 550 .venv/bin/python tools/$t.py > build/m23_$t.out 2>&1; echo "$t exit $? : $(tail -1 build/m23_$t.out | cut -c1-70)"
done | tee -a build/m23_gates.out
timeout 300 .venv/bin/python tools/m22_stack.py > build/m23_stack.out 2>&1; echo "m22_stack exit $? : $(grep -E 'deepest|gap' build/m23_stack.out | head -1)" | tee -a build/m23_gates.out
grep -E '^(hi_end)\s' build/kea48.sym | tee -a build/m23_gates.out
sha256sum build/killemall48_m23.tap build/killemall48_m22.tap | cut -c1-16,66- | tee -a build/m23_gates.out
ls -l build/killemall48_m23.tap | awk '{print "m23 tape", $5, "B"}' | tee -a build/m23_gates.out