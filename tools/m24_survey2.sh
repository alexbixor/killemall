#!/bin/bash
# M2.4 survey 2: free bytes, sprite data sizes, DRAM layout, draw cost baseline (read-only)
cd ~/work/killemall || exit 1
echo "== hi block gap"; grep -E "^(hi_end|fl_end|fl_set|HTABN|FL_D4|RECIP)\s" build/kea48.sym | tr '\n' ' '; echo
awk '$1=="hi_end"{print "hi_end", $3} $1=="fl_end"{print "fl_end", $3}' build/kea48.sym
echo "== sprite sizes"; grep -nE "^spr_[0-9]+:" src/gen/sprites_data.asm | head -20; grep -n "total" src/gen/sprites_data.asm
echo "== low block end"; grep -E "^(level_data|SCHAIN_END|SCHAIN|spr_table|start)\s" build/kea48.sym
echo "== level_data org / size"; grep -n "level_data" src/48k/kea48.asm | head -5; ls -la src/48k/gen/level48.bin build/level48_02.blk
echo "== DRAM (state.asm)"; grep -nE "DRAM|ds_rmin|ROWTAB|vis|things|zbuf|ATTRBUF|defs|equ" src/common/state.asm | head -40
echo "== sprite draw cost baseline"; timeout 300 .venv/bin/python tools/test_game_sprites.py 2>&1 | tail -15
echo "== CLRBUF tail / COPYBUF gen"; grep -nE "COPYBUF|ATTRCOPY|ret\"|jp render|CLRBUF" tools/gen48.py | head -12
