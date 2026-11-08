#!/bin/bash
# m29_restore.sh: put the pre-M2.9 sources back (build/pre_m29), so m29_try.sh starts from the original
cd /home/ubuntu/work/killemall
for f in kea48.asm sprites_b.asm sprites_d.asm game_d.asm game_a.asm game_e.asm hud_b.asm; do
  d=src/common; [ $f = kea48.asm ] && d=src/48k
  cp -p build/pre_m29/$f $d/$f
done
cp -p build/pre_m29/mknex.py tools/mknex.py
cp -p build/pre_m29/make_release.py tools/make_release.py
echo restored
