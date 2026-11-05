#!/usr/bin/env python3
"""test_tint.py (M2.5) - Python Z80-core oracle test of the per-level window tint.
For level 0/1/2 (+ a stale value 5, masked to 1): init_game must leave all 12 x 16 window attribute cells equal to TINTTAB[level],
the frame columns 7 / 24 and the HUD rows 13..23 unchanged, and render must keep the tint (no attribute writes).
usage: test_tint.py   (exit 0 = PASS)"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test48 import SYM
from test_game_sprites import machine, call, set_player, clear_things, set_thing
from p2e_oracle import engine_expectation        # M2.6 P2E

ATTRWIN = 22564          # M2.5C: window cols 4..27, frame cols 3 / 28
def win(m): return [m.memory[ATTRWIN + 32 * r + c] for r in range(12) for c in range(24)]
def frame(m): return [m.memory[ATTRWIN + 32 * r - 1] for r in range(12)] + [m.memory[ATTRWIN + 32 * r + 24] for r in range(12)]

def main():
    fails = 0
    m = machine()
    call(m, "cls", "hud_init")
    tab = bytes(m.memory[SYM["TINTTAB"]:SYM["TINTTAB"] + 4])
    print("TINTTAB", list(tab), "(level 1 Entry, 2 Barracks, 3 Furnace, spare)")
    if tab[:3] != bytes([7, 5, 6]): print("   FAIL: expected white, cyan, yellow"); fails += 1
    hud0, fr0 = bytes(m.memory[22528 + 13 * 32: 22528 + 24 * 32]), frame(m)
    for lvl in (0, 1, 2, 5, 0):
        m.set_memory_block(SYM["level"], bytes([lvl]))
        call(m, "init_game")
        want = tab[lvl & 3]
        w = win(m)
        bad = [i for i, v in enumerate(w) if v != want]
        set_player(m, 3.5, 7.5, 0); clear_things(m); set_thing(m, 0, 2, 5.0, 7.5); call(m, "render")
        exp = engine_expectation(m, want); w2 = win(m); bad2 = [i for i, v in enumerate(w2) if v != exp[i // 24][i % 24]]   # M2.6 P2E
        hud_ok = bytes(m.memory[22528 + 13 * 32: 22528 + 24 * 32]) == hud0 and frame(m) == fr0
        print("level byte %d -> ink %d: window cells wrong after init_game %d, after render %d, frame+HUD unchanged %s" % (lvl, want, len(bad), len(bad2), hud_ok))
        if bad or bad2 or not hud_ok: fails += 1
    print("RESULT", "PASS" if not fails else "FAIL %d" % fails)
    sys.exit(1 if fails else 0)

if __name__ == "__main__":
    main()
