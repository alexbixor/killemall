#!/bin/bash
# m22_survey17.sh - read-only: thing_xform hv/c0/nc (for the 0.8 enemy scale), ray loop texture page + floor ink registers
cd ~/work/killemall
echo "== sprites_b 100-150"; sed -n 100,150p src/common/sprites_b.asm
echo "== kea48 636-668 (ATTR regs)"; sed -n 636,668p src/48k/kea48.asm
echo "== kea48 684-730 (band / texture page)"; sed -n 684,730p src/48k/kea48.asm
echo "== band routine sample (gen48 emit_band)"; grep -n "def emit_band" -A30 tools/gen48.py | head -45
echo "== game_e 84-100"; sed -n 84,100p src/common/game_e.asm
echo "== NCTAB formula"; grep -n "nctab\s*=\|nctab =" tools/gen48.py
