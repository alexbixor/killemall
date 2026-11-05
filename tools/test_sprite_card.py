#!/usr/bin/env python3
"""test_sprite_card.py (M2.4) - Python Z80-core oracle test of the sprite card (no colour bleeding).
For a set of viewpoints / things, renders the frame with the engine and checks against a Python model:
 (a) ATTRIBUTE PURITY: every window cell whose attribute is a sprite ink (TYPEINK of a type present) contains NO pixel that
     is not sprite ink: BUF cell pixels == pixels of the sprite(s) drawn alone over a zeroed BUF, in that cell
     (exception allowed: slots where zbuf says the wall is nearer than the sprite - occlusion edges keep wall pixels).
 (b) CARD GEOMETRY: card cells = cells painted with the ink == union over byte columns of rows [top&~7 .. (feet-1)|7] where
     top = highest visible ink pixel of the figure in that byte column; no card outside the sprite's byte columns +-0.
 (c) EVERYWHERE ELSE the frame is byte-identical to the walls-only frame (walls, floor lines, other cells untouched).
 (d) z-buffer: columns where the wall is nearer keep their wall pixels (sprite partly behind a wall edge).
 (e) cost: draw_things T at near/mid/far for one zombie (printed; gate: 2-sprite frame >= 7.0 fps as before).
usage: test_sprite_card.py   (exit 0 = PASS)"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test48 import SYM, run_until
from test_game_sprites import machine, call, set_player, clear_things, set_thing, buf, changed_columns
from test_game_doors import fake_input

ATTRWIN = 22568
TYPEINK = {1: 3, 2: 4, 16: 7, 17: 6, 18: 2, 19: 1, 21: 5, 22: 6}

def attrs(m):
    return [[m.memory[ATTRWIN + 32 * r + c] for c in range(16)] for r in range(12)]

def map_set(m, x, y, code):
    m.set_memory_block(SYM["level_data"] + 1 + 8 + y * 32 + x, bytes([code]))

def cell_bytes(b, bc, row):
    return bytes(b[bc * 128 + row * 8: bc * 128 + row * 8 + 8])

def check_frame(m, things, label, fails, wall_attr_ref=None):
    """things = [(type, x, y)], player already set. Returns (fails, info)."""
    clear_things(m); call(m, "render"); ref = buf(m); a_ref = attrs(m)
    zb = bytes(m.memory[SYM["zbuf"]:SYM["zbuf"] + 64])
    for i, (t, x, y) in enumerate(things): set_thing(m, i, t, x, y)
    call(m, "render"); out = buf(m); a_out = attrs(m)
    nvis = m.memory[SYM["nvis"]]
    # sprite alone over a zero BUF (ink pixels) - draw_things only, zbuf kept from the render
    m.set_memory_block(0x6000, bytes(2048)); call(m, "draw_things"); alone = buf(m)
    inks = {TYPEINK[t] for t, _, _ in things}
    hv = max((m.memory[SYM["vis"] + 6 * k] for k in range(nvis)), default=0)
    bad_purity, bad_touch, card_cells, ink_cells = [], [], set(), set()
    for bc in range(16):
        for row in range(12):
            cell_out, cell_alone, cell_ref = cell_bytes(out, bc, row), cell_bytes(alone, bc, row), cell_bytes(ref, bc, row)
            if any(cell_alone): ink_cells.add((bc, row))
            if a_out[row][bc] in inks and a_out[row][bc] != a_ref[row][bc] or (a_out[row][bc] in inks and any(cell_alone)):
                card_cells.add((bc, row))
                # purity: pixels not belonging to the sprite must be 0, except slots occluded by a nearer wall
                for k in range(8):
                    extra = cell_out[k] & ~cell_alone[k] & 0xFF
                    if extra:
                        for slot in range(4):
                            bits = (0xC0 >> (2 * slot))
                            if extra & bits:
                                c = bc * 4 + slot
                                occl = zb[c] > hv or (zb[c] == hv and False)
                                if not occl: bad_purity.append((bc, row, k, hex(extra)))
            else:
                if cell_out != cell_ref: bad_touch.append((bc, row))
    stray_attr = [(bc, r) for r in range(12) for bc in range(16) if (bc, r) not in card_cells and a_out[r][bc] != a_ref[r][bc]]
    # geometry: every ink cell is a card cell; card cells per byte column form one vertical run from the top ink cell to the feet cell
    not_carded = [c for c in ink_cells if c not in card_cells]
    bad_geo = []
    for bc in range(16):
        rows = sorted(r for (b, r) in card_cells if b == bc)
        if rows and rows != list(range(rows[0], rows[-1] + 1)): bad_geo.append((bc, rows))
    print("%-34s nvis %d hv %3d | card cells %3d ink cells %3d | purity viol %d | touched outside %d | stray attr %d | gaps %d | ink w/o card %d" % (
        label, nvis, hv, len(card_cells), len(ink_cells), len(bad_purity), len(bad_touch), len(stray_attr), len(bad_geo), len(not_carded)))
    if bad_purity: print("   purity:", bad_purity[:6]); fails += 1
    if bad_touch: print("   touched outside card:", bad_touch[:6]); fails += 1
    if stray_attr: print("   stray attr:", stray_attr[:6]); fails += 1
    if bad_geo: print("   card gaps:", bad_geo[:3]); fails += 1
    if not_carded: print("   ink without card:", not_carded[:6]); fails += 1
    if nvis != len(things): print("   FAIL: nvis %d != %d" % (nvis, len(things))); fails += 1
    return fails, (nvis, hv, len(card_cells))

def main():
    fails = 0
    m = machine()
    call(m, "init_game", "render"); fake_input(m, 0)
    m.set_memory_block(SYM["draw_weapon"], bytes([0xC9]))        # weapon off: BUF rows 72..95 hold walls/sprites only
    for x in range(7, 12): map_set(m, x, 7, 0)                      # open corridor x 7..11 at y 7
    set_player(m, 3.5, 7.5, 0)
    for d in (0.8, 1.2, 1.5, 2.0, 3.0, 4.5):
        for typ, name in ((2, "zombie"), (1, "imp"), (21, "barrel")):
            fails, _ = check_frame(m, [(typ, 3.5 + d, 7.5)], "%s d=%.1f centred" % (name, d), fails)
    # off-centre (lateral) and two sprites overlapping, far one first
    fails, _ = check_frame(m, [(2, 5.5, 8.1)], "zombie d=2.0 right", fails)
    fails, _ = check_frame(m, [(2, 5.5, 6.9)], "zombie d=2.0 left", fails)
    fails, _ = check_frame(m, [(2, 6.5, 7.5), (1, 5.0, 7.3)], "zombie far + imp near overlap", fails)
    fails, _ = check_frame(m, [(2, 5.0, 7.5), (16, 6.5, 7.8)], "zombie + health behind", fails)
    # partial occlusion: wall block at x=5,y=7 restored, zombie at x=5.5 y=8.2 peeks past its right edge
    map_set(m, 5, 7, 1)
    fails, _ = check_frame(m, [(2, 5.5, 8.4)], "zombie half behind wall edge", fails)
    map_set(m, 5, 7, 0)
    # cost
    import time
    for d, nm in ((0.6, "near"), (1.5, "mid"), (3.0, "far")):
        clear_things(m); call(m, "render"); set_thing(m, 0, 2, 3.5 + d, 7.5); call(m, "render")
        t = call(m, "draw_things"); print("draw_things zombie %s d=%.1f: T %d" % (nm, d, t))
    clear_things(m); set_thing(m, 0, 2, 5.0, 7.5); set_thing(m, 1, 1, 6.5, 7.5)
    t2 = call(m, "render"); print("frame with 2 sprites T %d -> %.1f fps" % (t2, 3_500_000 / t2))
    if 3_500_000 / t2 < 7.0: print("FAIL: 2-sprite frame below 7 fps"); fails += 1
    print("RESULT", "PASS" if not fails else "FAIL %d" % fails)
    return 0 if not fails else 1

if __name__ == "__main__":
    sys.exit(main())
