#!/usr/bin/env python3
"""m26_dbg_occl.py - why does test_sprite_scale (e) see 'attr changed' with 0 changed pixels? Hypothesis: silhouette() calls
draw_things OUTSIDE render (no attr_write afterwards), so the imp's CMIN marks from block (d) survive into (e)'s walls-only
render, which then shows magenta cells in a0; the barrel frame has no marks -> differs. Replicates (d) -> (e) and prints CMIN."""
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "tools"))
from test48 import SYM
from test_game_sprites import machine, call, set_player, clear_things, set_thing, buf, changed_columns
from test_game_doors import fake_input
from test_sprite_scale import map_set, silhouette, attrs, vis_entries
def cmin(m): return [(i, m.memory[SYM["CMIN"] + i]) for i in range(48) if m.memory[SYM["CMIN"] + i]]
m = machine(); call(m, "init_game", "render"); fake_input(m, 0)
m.set_memory_block(SYM["draw_weapon"], bytes([0xC9]))
for x in range(7, 12): map_set(m, x, 7, 0)
# (d) saturation, as in the test
map_set(m, 4, 7, 1)
set_player(m, 3.5, 7.5, 0); clear_things(m); call(m, "render")
set_thing(m, 0, 1, 3.9, 7.5); call(m, "render"); v = vis_entries(m)
print("(d) after render: vis", v, "CMIN", cmin(m))
top, bot, cols = silhouette(m)
print("(d) after silhouette (draw_things x2 outside render): CMIN", cmin(m))
map_set(m, 4, 7, 0)
# (e) occlusion
map_set(m, 7, 7, 1)
set_player(m, 3.5, 7.5, 0); clear_things(m); call(m, "render"); ref = buf(m); a0 = attrs(m)
print("(e) walls-only: distinct attr values", sorted({v for r in a0 for v in r}), "CMIN after", cmin(m))
set_thing(m, 0, 21, 8.5, 7.5); call(m, "render"); cols, pix = changed_columns(ref, buf(m)); a1 = attrs(m)
d = [(r, c, a0[r][c], a1[r][c]) for r in range(12) for c in range(24) if a0[r][c] != a1[r][c]]
print("(e) barrel: changed pixels", len(pix), "attr cells differing (row, col, walls-only, barrel):", len(d), d[:12])
print("(e) barrel frame distinct attr values", sorted({v for r in a1 for v in r}), "CMIN after", cmin(m))
