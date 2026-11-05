#!/usr/bin/env python3
"""m24_dbg_card.py - dump the card/ink rows per byte column for one sprite at one distance (Python Z80 oracle), to see why
test_sprite_scale reports a silhouette top above the sprite for items at some distances."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path.home() / "work/killemall/tools"))
from test48 import SYM
from test_game_sprites import machine, call, set_player, clear_things, set_thing, buf
from test_game_doors import fake_input
from test_sprite_scale import map_set

typ, dist = int(sys.argv[1]), float(sys.argv[2])
m = machine(); call(m, "init_game", "render"); fake_input(m, 0)
m.set_memory_block(SYM["draw_weapon"], bytes([0xC9]))
for x in range(7, 12): map_set(m, x, 7, 0)
wall_x = int(3.5 + dist + 1)
map_set(m, wall_x, 7, 1)
set_player(m, 3.5, 7.5, 0); clear_things(m); set_thing(m, 0, typ, 3.5 + dist, 7.5)
call(m, "render")
vis = bytes(m.memory[SYM["vis"]:SYM["vis"] + 6]); print("vis hv c0 nc:", vis[0], vis[1] - 256 if vis[1] > 127 else vis[1], vis[2])
m.set_memory_block(0x6000, bytes(2048)); call(m, "draw_things"); white = buf(m)
m.set_memory_block(0x6000, bytes([0xFF]) * 2048); call(m, "draw_things"); black = buf(m)
for bc in range(16):
    w_rows = [r for r in range(96) if white[bc * 128 + r]]
    b_rows = [r for r in range(96) if black[bc * 128 + r] != 0xFF]
    if w_rows or b_rows:
        print("bc %2d ink rows %s..%s (%d)  card/black rows %s..%s (%d)" % (bc, min(w_rows) if w_rows else None, max(w_rows) if w_rows else None, len(w_rows),
              min(b_rows) if b_rows else None, max(b_rows) if b_rows else None, len(b_rows)))
rt = [m.memory[SYM["ROWTAB"] + 2 * i] | (m.memory[SYM["ROWTAB"] + 2 * i + 1] << 8) for i in range(25)]
print("ROWTAB:", rt)
