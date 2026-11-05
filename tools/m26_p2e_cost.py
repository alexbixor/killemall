#!/usr/bin/env python3
"""m26_p2e_cost.py - render cost of the pre-M2.6 tape (build/pre_m26/killemall48_m25.tap, M2.5E) vs the current P2E build, same
views, same harness (Python Z80 core, T-states of one 'render' call = CLRBUF + 64 rays + sprites + COPYBUF [+ attr_write])."""
import sys, struct, pathlib, re
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import z80
from test48 import run_until
ROOT = pathlib.Path(__file__).resolve().parents[1]

def tap_blocks(p):
    d = p.read_bytes(); i = 0; out = []
    while i < len(d):
        n = struct.unpack_from("<H", d, i)[0]; out.append(d[i + 2:i + 2 + n]); i += 2 + n
    return out

def syms(p):
    S = {}
    for l in open(p):
        m = re.match(r"(\S+)\s+EQU\s+([0-9A-F]+)H", l)
        if m: S[m.group(1)] = int(m.group(2), 16)
    return S

def load(tap, sym):
    bl = tap_blocks(tap)
    for k, b in enumerate(bl):
        if b[0] == 0 and b[1] == 3 and b[2:12] == b"killemall ":
            start = struct.unpack_from("<H", b, 14)[0]; code = bl[k + 1][1:-1]; break
    m = z80.Z80Machine(); m.set_memory_block(start, code); m.set_memory_block(0x5EF0, bytes([0xC3, 0xF0, 0x5E]))
    S = syms(sym)
    data = (ROOT / "src/48k/gen/level48.bin").read_bytes()
    m.set_memory_block(S["level_data"], data); m.set_memory_block(S["level"], bytes([0]))
    return m, S

def call(m, S, *labels):
    prog = b"".join(bytes([0xCD]) + S[l].to_bytes(2, "little") for l in labels) + bytes([0xC3, 0xF0, 0x5E])
    m.set_memory_block(0x5EC0, prog); m.pc = 0x5EC0; m.sp = 65008
    return run_until(m, 0x5EF0)

def set_player(m, S, px, py, ang):
    ix, fx = int(px), int((px - int(px)) * 256); iy, fy = int(py), int((py - int(py)) * 256)
    m.set_memory_block(S["posx"], bytes([fx, ix])); m.set_memory_block(S["posy"], bytes([fy, iy]))
    m.set_memory_block(S["angle"], bytes([ang & 255]))

def set_thing(m, S, i, typ, x, y):
    ix, fx = int(x), int((x - int(x)) * 256); iy, fy = int(y), int((y - int(y)) * 256)
    m.set_memory_block(S["things"] + 8 * i, bytes([typ, fx, ix, fy, iy, 0, 30, 0]))

VIEWS = (("start+zombie 2.5", (3.5, 7.5, 0), [(2, 6.0, 7.5)]), ("imp 1.5 / wall", (5.0, 2.6, 0), [(1, 6.5, 2.6)]),
         ("start empty", (3.5, 7.5, 0), []), ("3 enemies 1.5-3", (3.5, 7.5, 0), [(2, 5.0, 7.5), (1, 6.0, 7.0), (2, 6.5, 8.0)]))
if __name__ == "__main__":
    res = {}
    for label, tap, sym in (("M2.5E", ROOT / "build/pre_m26/killemall48_m25.tap", ROOT / "build/pre_m26/kea48.sym"),
                            ("M2.6", ROOT / "build/killemall48_m25.tap", ROOT / "build/kea48.sym")):
        m, S = load(tap, sym); call(m, S, "cls", "hud_init", "init_game")
        for name, (px, py, ang), things in VIEWS:
            set_player(m, S, px, py, ang); m.set_memory_block(S["things"], bytes(128))
            for i, (t, x, y) in enumerate(things): set_thing(m, S, i, t, x, y)
            res[(label, name)] = call(m, S, "render")
    for name, _, _ in VIEWS:
        a, b = res[("M2.5E", name)], res[("M2.6", name)]
        print("%-18s M2.5E %7d T %.2f fps | M2.6 D5+P2E %7d T %.2f fps | +%d T = +%.1f%%" % (name, a, 3.5e6 / a, b, 3.5e6 / b, b - a, 100.0 * (b - a) / a))
