#!/bin/bash
# M2.4 survey: memory room for a sprite black-box erase + sprite art pipeline facts (read-only)
cd ~/work/killemall || exit 1
echo "== build report tail (padding / hi_end)"; tail -12 build/m22_build_last.log 2>/dev/null
echo "== m23 build script"; cat tools/build_m23_48.sh
echo "== low block symbols (sprites48 org 27904): end markers"; grep -iE "SCHAIN_END|lo_end|LOW_END|level|spr_17|dash_end|SPG" build/kea48.sym | head -12
echo "== sprite code symbols"; grep -E "^(ds_cols|dc_attr|dc_mark|dc_next|dc_run|draw_sprite|vis_sort_draw|draw_things|TYPEINK|ROWTAB|SLOTM|zbuf|ATTRBUF|BUF|hi_end|fl_set|FL_D4|HTABN|CLRBUF|COPYBUF|ATTRCOPY) " build/kea48.sym
echo "== gen48 padding/align handling"; grep -nE "pad|align|ALIGN|fl_|floor|92|hi_end" tools/gen48.py | head -30
echo "== dead code (m23_deadcode.py)"; .venv/bin/python tools/m23_deadcode.py 2>/dev/null | head -20
echo "== sprite data budget"; grep -nE "total|bytes" src/gen/sprites_data.asm | head -5; grep -nE "spritec|sprites_data" tools/gen48.py tools/build_m23_48.sh | head
echo "== test tools for sprites"; sed -n 1,40p tools/test_game_sprites.py
echo "== profiler"; ls tools | grep -iE "prof|fps|perf" ; grep -n "def fps\|fps" tools/m23_shots.py | head -5
