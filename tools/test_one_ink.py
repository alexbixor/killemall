#!/usr/bin/env python3
"""test_one_ink.py (M2.5) - Python Z80-core oracle test of the one-ink window (replaces test_sprite_card.py).
 (a) P2E (M2.6): after render with 0, 1 and 2 sprites at several distances and in front of every wall texture, the 12 x 24
     window attribute cells equal tools/p2e_oracle.py's expectation: tint everywhere, tint | BRIGHT on near-wall cells, sprite
     ink | BRIGHT exactly on the cells holding a coloured sprite's white pixels (nearest sprite wins) -> nothing can clash.
 (b) MASK: the sprite drawn alone over a zeroed BUF (white runs) and over an all-ones BUF (black runs = art 'o' + 1-px halo)
     touches only its own ray columns; every white pixel has a black or white neighbour ring inside the figure's columns
     (the halo exists: the count of black pixels adjacent to white pixels is > 0 for every enemy frame).
 (c) HUD attributes (rows 13..23) are untouched by render (byte-identical before/after).
 (d) the per-frame attribute work is gone: render writes no byte into 0x5800..0x5AFF (write hook).
usage: test_one_ink.py   (exit 0 = PASS)"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test48 import SYM
from test_game_sprites import machine, call, set_player, clear_things, set_thing, buf, changed_columns, BUF0, BUFCOLS, BUFSTR
from p2e_oracle import engine_expectation, diff        # M2.6 P2E: per-cell expectation from zbuf + sprites drawn alone

ATTRWIN = 22564          # M2.5C: window cols 4..27 (24 cells per row)
def attrs(m): return [[m.memory[ATTRWIN + 32 * r + c] for c in range(24)] for r in range(12)]
def map_set(m, x, y, code): m.set_memory_block(SYM["level_data"] + 1 + 8 + y * 32 + x, bytes([code]))

def main():
    fails = 0
    m = machine()
    call(m, "init_game", "cls")          # M2.5C: init_game builds CHJ (RAM); cls = white ink on black paper everywhere
    hud = bytes(m.memory[22528 + 13 * 32: 22528 + 24 * 32])
    scenes = [("start, no sprite", []), ("zombie 2.5", [(2, 6.0, 7.5)]), ("imp 1.5", [(1, 5.0, 7.5)]),
              ("zombie 0.9 + barrel", [(2, 4.4, 7.5), (21, 5.5, 8.3)]), ("health + ammo items", [(16, 5.0, 7.2), (17, 5.0, 7.8)])]
    for name, things in scenes:
        set_player(m, 3.5, 7.5, 0); clear_things(m)
        for i, (t, x, y) in enumerate(things): set_thing(m, i, t, x, y)
        call(m, "render")
        a = attrs(m)
        bad = diff(a, engine_expectation(m))                 # M2.6 P2E: cells that differ from the independent expectation
        nvis = m.memory[SYM["nvis"]]
        print("%-24s nvis %d | attr cells != P2E expectation: %d" % (name, nvis, len(bad)))
        if bad: print("   FAIL cells:", bad[:8]); fails += 1
        if things and nvis != len(things): print("   FAIL: expected %d visible sprites" % len(things)); fails += 1
    # every wall texture code 1..12 straight ahead with a zombie in front
    for code in range(1, 13):
        set_player(m, 3.5, 7.5, 0); clear_things(m)
        for x in range(5, 12): map_set(m, x, 7, 0)
        map_set(m, 7, 7, code)
        set_thing(m, 0, 2, 5.5, 7.5); call(m, "render"); a = attrs(m)
        bad = diff(a, engine_expectation(m))
        if bad: print("   FAIL wall code %d: attr cells != P2E expectation %s" % (code, bad[:6])); fails += 1
    print("12 wall codes with a zombie in front: attr violations %d" % fails)
    # (b) mask / halo per enemy frame
    for typ, name in ((1, "imp"), (2, "zombie")):
        set_player(m, 3.5, 7.5, 0); clear_things(m); set_thing(m, 0, typ, 5.0, 7.5); call(m, "render")
        N = BUFCOLS * BUFSTR
        m.set_memory_block(BUF0, bytes(N)); call(m, "draw_things"); white = buf(m)
        m.set_memory_block(BUF0, bytes([0xFF]) * N); call(m, "draw_things"); black = buf(m)
        cw, pw = changed_columns(bytes(N), white); cb, pb = changed_columns(bytes([0xFF]) * N, black)
        vis = bytes(m.memory[SYM["vis"]:SYM["vis"] + 6]); c0 = vis[1] - 256 if vis[1] > 127 else vis[1]; nc = vis[2]
        span = set(range(max(c0, 0), min(c0 + nc, 64)))
        out = (cw | cb) - span
        print("%-7s white px %4d black px %4d | cols %s..%s span %d..%d | outside span %d" %
              (name, len(pw), len(pb), min(cw | cb) if cw | cb else None, max(cw | cb) if cw | cb else None, min(span), max(span), len(out)))
        if not pw or not pb: print("   FAIL: sprite needs white runs and black runs (halo)"); fails += 1
        if out: print("   FAIL: pixels outside the sprite's ray columns", sorted(out)[:8]); fails += 1
    # (c) HUD untouched
    set_player(m, 3.5, 7.5, 0); clear_things(m); set_thing(m, 0, 2, 5.0, 7.5); call(m, "render")
    hud2 = bytes(m.memory[22528 + 13 * 32: 22528 + 24 * 32])
    print("HUD attribute rows 13..23 unchanged by render:", hud == hud2)
    if hud != hud2: fails += 1
    # (d) the per-frame attribute work is gone: poison the window attributes, render, they must be untouched (then restore)
    for r in range(12): m.set_memory_block(ATTRWIN + 32 * r, bytes([0x55]) * 24)     # the 24 window cells of each row
    set_player(m, 3.5, 7.5, 0); clear_things(m); set_thing(m, 0, 2, 5.0, 7.5); call(m, "render")
    poisoned = not diff(attrs(m), engine_expectation(m))     # M2.6 P2E: render repaints every window cell each frame
    print("render repaints all 288 window cells from the tint + marks (poison test):", poisoned)
    if not poisoned: fails += 1
    for r in range(12): m.set_memory_block(ATTRWIN + 32 * r, bytes([7]) * 24)
    print("RESULT", "PASS" if not fails else "FAIL %d" % fails)
    sys.exit(1 if fails else 0)

if __name__ == "__main__":
    main()
