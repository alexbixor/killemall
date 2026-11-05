#!/usr/bin/env python3
"""debug: does today's engine draw the zombie in this harness? Compare BUF with/without the thing, dump vis/zbuf, save PNGs."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test48 import SYM, ROOT
from test_game_sprites import machine, call, clear_things, set_thing, buf, changed_columns
from run48 import scr_to_png
m = machine()
data = (ROOT / "src/48k/gen/level48.bin").read_bytes()
m.set_memory_block(SYM["level_data"], data); m.set_memory_block(SYM["level"], bytes([0]))
call(m, "cls", "hud_init", "init_game")
sx, sy, ang = m.memory[SYM["posx"] + 1], m.memory[SYM["posy"] + 1], m.memory[SYM["angle"]]
print("start", sx, sy, "angle", ang, "posx frac", m.memory[SYM["posx"]], "posy frac", m.memory[SYM["posy"]])
clear_things(m); call(m, "render", "hud_update"); ref = buf(m)
scr0 = bytes(m.memory[16384:16384 + 6912])
for dist in (1.0, 1.5):
    dx, dy = {0: (dist, 0), 64: (0, dist), 128: (-dist, 0), 192: (0, -dist)}.get(ang, (dist, 0))
    clear_things(m); set_thing(m, 0, 2, sx + 0.5 + dx, sy + 0.5 + dy)
    print("thing bytes", list(m.memory[SYM["things"]:SYM["things"] + 8]))
    call(m, "render", "hud_update")
    b = buf(m); cols, pix = changed_columns(ref, b)
    vis = list(m.memory[SYM["vis"]:SYM["vis"] + 6]); nvis = m.memory[SYM["nvis"]]
    zb = list(m.memory[SYM["zbuf"]:SYM["zbuf"] + 64])
    scr = bytes(m.memory[16384:16384 + 6912])
    print("dist", dist, "nvis", nvis, "vis", vis, "changed byte cols", cols, "pixels", pix, "screen bytes differ from no-thing", sum(1 for i in range(6144) if scr[i] != scr0[i]))
    print("zbuf", zb)
    scr_to_png(scr, str(ROOT / ("build/m26_dbg_%.1f.png" % dist)))
print("thing types in level (THSPR):", list(m.memory[SYM["THSPR"]:SYM["THSPR"] + 8]) if "THSPR" in SYM else "no THSPR sym")
