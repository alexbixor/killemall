#!/usr/bin/env python3
"""m21_before.py - same measurements as test_sprite_scale (saturation + adjacent-enemy depth + attribute colours) on the
PRE-fix build (build/kea48_pre_m21.tap + .sym) for the before/after table of build/m21_report.md."""
import sys, pathlib, re
sys.path.insert(0, "/home/ubuntu/work/killemall/tools")
import test48
ROOT = pathlib.Path("/home/ubuntu/work/killemall")
SYM = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", (ROOT / "build/kea48_pre_m21.sym").read_text(), re.M)}
test48.SYM.clear(); test48.SYM.update(SYM)
import test_game_sprites as tgs
tgs.SYM = SYM
orig_load = test48.load_code
def load_code():
    blocks = test48.tap_blocks(ROOT / "build/kea48_pre_m21.tap")
    for h, d in zip(blocks[::2], blocks[1::2]):
        if h[0] == 0 and h[1] == 3:
            return h[14] | (h[15] << 8), bytes(d[1:-1])
test48.load_code = load_code; tgs.load_code = load_code
from test_game_sprites import machine, call, set_player, clear_things, set_thing, buf, changed_columns
ATTRWIN = 22568
def attrs(m): return [[m.memory[ATTRWIN + 32 * r + c] for c in range(16)] for r in range(12)]
def map_set(m, x, y, code): m.set_memory_block(SYM["level_data"] + 1 + 8 + y * 32 + x, bytes([code]))
m = machine(); call(m, "init_game", "render"); m.set_memory_block(SYM["draw_weapon"], bytes([0xC9]))
# adjacent enemy in front of a near wall (both at the 128 cap): drawn?
map_set(m, 4, 7, 1)
set_player(m, 3.5, 7.5, 0); clear_things(m); call(m, "render"); ref = buf(m)
set_thing(m, 0, 1, 3.9, 7.5); call(m, "render"); cols, pix = changed_columns(ref, buf(m))
print("BEFORE adjacent imp (0.4 cell) in front of wall at 0.5 cell: nvis %d, changed pixels %d (0 = invisible)" % (m.memory[SYM["nvis"]], len(pix)))
map_set(m, 4, 7, 0)
# barrel at 1.5 in front of the level wall at 3.5: attribute cells of the sprite area vs the wall
set_player(m, 3.5, 7.5, 0); clear_things(m); call(m, "render"); ref = buf(m); a0 = attrs(m)
set_thing(m, 0, 21, 5.0, 7.5); call(m, "render"); out = buf(m); a1 = attrs(m)
cols, pix = changed_columns(ref, out); rows = [r for c, r in pix]
print("BEFORE barrel d=1.5: rows %d..%d (16-row asset: top %d vs horizon 48), attrs changed by the sprite: %s" % (min(rows), max(rows), min(rows), a1 != a0))
cells = sorted({(c // 4, r // 8) for c, r in pix}); print("   sprite cells and their attrs (wall ink/paper):", [(bc, r, a1[r][bc]) for bc, r in cells][:12])
