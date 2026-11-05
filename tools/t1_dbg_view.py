#!/usr/bin/env python3
"""t1_dbg_view.py - render a viewpoint with and without things; print vis list and changed-column summary."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test_game_sprites import machine, call, set_player, clear_things, buf, changed_columns, SYM
px, py, ang = float(sys.argv[1]), float(sys.argv[2]), int(sys.argv[3])
m = machine(); call(m, "init_game")
set_player(m, px, py, ang)
t1 = call(m, "render"); out = buf(m)
nvis = m.memory[SYM["nvis"]]
print("T with things", t1, "nvis", nvis)
for i in range(nvis):
    v = bytes(m.memory[SYM["vis"] + 6 * i: SYM["vis"] + 6 * i + 6])
    print(" vis", i, "hv", v[0], "c0", v[1] - 256 if v[1] > 127 else v[1], "nc", v[2], "spr %04x" % (v[3] | v[4] << 8), "thing", v[5])
th = SYM["things"]
for i in range(16):
    r = bytes(m.memory[th + 8 * i: th + 8 * i + 8])
    if r[0]: print(" thing", i, "type", r[0], "x %.2f y %.2f" % (r[2] + r[1] / 256, r[4] + r[3] / 256), "state", r[5])
print("cos7 %d sin7 %d" % (m.memory[SYM["cos7"]] - (256 if m.memory[SYM["cos7"]] > 127 else 0), m.memory[SYM["sin7"]] - (256 if m.memory[SYM["sin7"]] > 127 else 0)))
clear_things(m); t0 = call(m, "render"); ref = buf(m)
cols, pix = changed_columns(ref, out)
print("T walls only", t0, "changed cols", sorted(cols)[:5], "...", len(cols), "pixels", len(pix))

pathlib.Path("build/t1_dbg_scr.bin").write_bytes(bytes(m.memory[0x4000:0x5B00]))
# FTX/FTY integrity: word k*frac for k = 0..255 (the walls-only render is the last one)
fx, fy = m.memory[SYM["posx"]], m.memory[SYM["posy"]]
for name, base, fr in (("FTX", 0x6800, fx), ("FTY", 0x6B00, fy)):
    bad = [k for k in range(256) if (m.memory[base + 2 * k] | m.memory[base + 2 * k + 1] << 8) != (k * fr) % 65536]
    print(name, "frac", fr, "bad entries", len(bad), bad[:6])
