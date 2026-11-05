#!/usr/bin/env python3
"""m21_cycles.py - cycle-exact render cost, M2 (build/kea48_pre_m21.tap) vs M2.1 (build/kea48.tap), same scenes, Python Z80
core. render = rays + bands + sprites + (M2.1: ATTRCOPY) + COPYBUF; weapon drawn; no ISR. Scenes:
  A start view, no things;  B start view, level things (barrel + health as placed by init_game);
  C near: corridor x=7..11 open, wall at x=6, barrel (5.0,7.05) + imp (5.0,7.95) at 1.5 cells (= m21_shots 'near');
  D mid: same at 3.0 cells (wall at x=8);  E far: same at 5.0 cells (wall at x=10).
Also checks that the code block inside build/killemall48_m21.tap is byte-identical to build/kea48.tap."""
import sys, pathlib, re, importlib
sys.path.insert(0, "/home/ubuntu/work/killemall/tools")
ROOT = pathlib.Path("/home/ubuntu/work/killemall")
import test48

def code_block(tap):
    blocks = test48.tap_blocks(tap)
    for h, d in zip(blocks[::2], blocks[1::2]):
        if h[0] == 0 and h[1] == 3 and len(d) > 20000:
            return h[14] | (h[15] << 8), bytes(d[1:-1])

def measure(tap, sym):
    SYM = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^(\w+)\s+EQU\s+0?([0-9A-F]+)H", (ROOT / sym).read_text(), re.M)}
    test48.SYM.clear(); test48.SYM.update(SYM)
    test48.load_code = lambda: code_block(ROOT / tap)
    import test_game_sprites as tgs
    importlib.reload(tgs); tgs.SYM = SYM; tgs.load_code = test48.load_code
    from test_game_doors import fake_input
    m = tgs.machine(); tgs.call(m, "init_game", "render"); fake_input(m, 0)
    def map_set(x, y, code): m.set_memory_block(SYM["level_data"] + 1 + 8 + y * 32 + x, bytes([code]))
    def t(): return tgs.call(m, "render")
    out = {}
    tgs.set_player(m, 3.5, 7.5, 0)
    things0 = bytes(m.memory[SYM["things"]:SYM["things"] + 128])
    tgs.clear_things(m); out["A start, no things"] = t()
    m.set_memory_block(SYM["things"], things0); out["B start, level things"] = t()
    for d, name in ((1.5, "C near 1.5"), (3.0, "D mid 3.0"), (5.0, "E far 5.0")):
        wx = int(3.5 + d + 1.0)
        for x in range(7, 12): map_set(x, 7, 1 if x == wx else 0)
        tgs.clear_things(m); tgs.set_thing(m, 0, 21, 3.5 + d, 7.05); tgs.set_thing(m, 1, 1, 3.5 + d, 7.95)
        out[name] = t()
    return out

m2 = measure("build/kea48_pre_m21.tap", "build/kea48_pre_m21.sym")
m21 = measure("build/kea48.tap", "build/kea48.sym")
print("scene                 M2 T      fps    M2.1 T    fps    delta T  delta %")
for k in m2:
    a, b = m2[k], m21[k]
    print("%-20s %8d  %5.1f  %8d  %5.1f  %+7d  %+5.1f%%" % (k, a, 3500000 / a, b, 3500000 / b, b - a, 100.0 * (b - a) / a))
s1, c1 = code_block(ROOT / "build/kea48.tap"); s2, c2 = code_block(ROOT / "build/killemall48_m21.tap")
print("code block kea48.tap %d bytes @%d; killemall48_m21.tap %d bytes @%d; identical: %s" % (len(c1), s1, len(c2), s2, c1 == c2))
