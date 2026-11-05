#!/usr/bin/env python3
"""m24_dbg_scale.py - replicate test_sprite_scale's sequence for one distance and dump per byte column ink/black rows per
asset, to see where the measured silhouette top comes from (M2.4 card vs stale state)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path.home() / "work/killemall/tools"))
from test48 import SYM
from test_game_sprites import machine, call, set_player, clear_things, set_thing, buf
from test_game_doors import fake_input
from test_sprite_scale import map_set, vis_entries

d = float(sys.argv[1]) if len(sys.argv) > 1 else 1.5
m = machine(); call(m, "init_game", "render"); fake_input(m, 0)
m.set_memory_block(SYM["draw_weapon"], bytes([0xC9]))
for x in range(7, 12): map_set(m, x, 7, 0)
wx = int(3.5 + d + 1.0)
for x in range(7, 12): map_set(m, x, 7, 1 if x == wx else 0)
for typ, name in ((1, "imp"), (21, "barrel"), (16, "health")):
    set_player(m, 3.5, 7.5, 0); clear_things(m); call(m, "render")
    set_thing(m, 0, typ, 3.5 + d, 7.5); call(m, "render")
    v = vis_entries(m); print(name, "vis", v)
    m.set_memory_block(0x6000, bytes(2048)); call(m, "draw_things"); white = buf(m)
    m.set_memory_block(0x6000, bytes([0xFF]) * 2048); call(m, "draw_things"); black = buf(m)
    for bc in range(16):
        w_rows = [r for r in range(96) if white[bc * 128 + r]]
        b_rows = [r for r in range(96) if black[bc * 128 + r] != 0xFF]
        if w_rows or b_rows:
            print("  bc %2d ink %s..%s (%d)  black %s..%s (%d)" % (bc, min(w_rows) if w_rows else None, max(w_rows) if w_rows else None, len(w_rows),
                  min(b_rows) if b_rows else None, max(b_rows) if b_rows else None, len(b_rows)))
    print("  ROWTAB:", list(m.memory[SYM["ROWTAB"]:SYM["ROWTAB"] + 25]))
