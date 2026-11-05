#!/bin/bash
# m25_survey4.sh - read-only: reference renderer, texture format, sprite projection constants, ROM calls / sysvars, levels
cd ~/work/killemall || exit 1
echo "== chk48.py head"; sed -n 1,60p tools/chk48.py
echo "== gen48.py textures"; grep -nE -B2 -A12 "def textures|TEX|texel" tools/gen48.py | sed -n 1,80p
echo "== sprites_b.asm (projection)"; sed -n 1,110p src/common/sprites_b.asm
echo "== ROM calls / sysvars"; grep -nE -i "call (0x0|[0-9]{3,4}\b)|rst |0x5c[0-9a-f]{2}|2367[0-9]|BORDCR|FRAMES|LD.?BYTES|1366|0x0556" src/48k/kea48.asm src/common/*.asm | grep -viE "defb|^\S+:[0-9]+:;" | head -30
echo "== IY usage"; grep -nE -i "\biy\b" src/48k/kea48.asm src/common/*.asm src/48k/gen/*.asm | head
echo "== levels"; grep -nE -i "level_data|next_level|load_level|LEVEL" src/common/game_*.asm src/48k/kea48.asm | head -20
echo "== apply_opts"; sed -n "$(grep -n '^apply_opts' src/48k/kea48.asm | cut -d: -f1),+12p" src/48k/kea48.asm
echo "== build_ftab"; sed -n "$(grep -n '^build_ftab' src/48k/kea48.asm | cut -d: -f1),+30p" src/48k/kea48.asm