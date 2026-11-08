#!/bin/bash
# m29_try.sh: apply M2.9 edit (twice, idempotence), build 48K + 128K, summarise to build/m29_try.out
cd /home/ubuntu/work/killemall
{
date -u +%H:%M:%SZ
python3 tools/m29_edit_steps.py
python3 tools/m29_edit_steps.py
bash tools/build_m25_48.sh > build/m29_build1.out 2>&1; echo "build48 rc=$?"
grep -E "hi_end|TOO|rror|free below" build/m29_build1.out | cut -c1-160
md5sum build/killemall48_m25.tap | cut -c1-16
bash tools/build128.sh > build/m29_build128.out 2>&1; echo "build128 rc=$?"
grep -iE "free|hi_end|TOO|rror|wrote" build/m29_build128.out | cut -c1-160 | tail -6
} > build/m29_try.out 2>&1
