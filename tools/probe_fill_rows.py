#!/usr/bin/env python3
"""probe_fill_rows.py - which byte of the CLRBUF fill words lands on which BUF row? Poke distinct words, render with lines off,
read an open byte column. Facts for step E, not assumptions."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test48 import SYM, ROOT
from test_game_sprites import machine, call, set_player, clear_things, buf, BUFCOLS, BUFSTR
m = machine()
data = (ROOT / "src/48k/gen/level48.bin").read_bytes()
m.set_memory_block(SYM["level_data"], data); m.set_memory_block(SYM["level"], bytes([0]))
call(m, "cls", "hud_init", "init_game")
m.set_memory_block(SYM["cl_de"] + 1, bytes([0x11, 0x22]))     # floor word: low 0x11, high 0x22
m.set_memory_block(SYM["cl_ce"] + 1, bytes([0x33, 0x44]))     # ceiling word: low 0x33, high 0x44
m.set_memory_block(SYM["fl_k"] + 1, bytes([0]))               # lines off
clear_things(m); set_player(m, 3.5, 7.5, 0)
m.set_memory_block(SYM["draw_weapon"], bytes([0xC9]))
call(m, "render")
b = buf(m)
# find the byte column with the shortest wall (most open rows): zbuf minimum
zb = [m.memory[SYM["zbuf"] + c] for c in range(64)]
c = min(range(64), key=lambda i: zb[i]); bc = 3 * (c >> 3) + [0, 0, 0, 1, 1, 2, 2, 2][c & 7]
print("ray", c, "zbuf", zb[c], "byte col", bc)
col = b[bc * BUFSTR: bc * BUFSTR + 96]
print("rows 0..11 :", " ".join("%02X" % v for v in col[0:12]))
print("rows 40..55:", " ".join("%02X" % v for v in col[40:56]))
print("rows 84..95:", " ".join("%02X" % v for v in col[84:96]))
print("floor word w covers rows 48+2w (byte %02X) and 49+2w (byte %02X)" % (col[48], col[49]))
print("ceiling: row 46 %02X row 47 %02X row 0 %02X row 1 %02X" % (col[46], col[47], col[0], col[1]))
# BC / BC' at render entry: dump registers before CLRBUF is not possible here; instead check that render output is unchanged
# when BC/BC' are poisoned before the call (proves CLRBUF does not depend on them) - done in the edit script's test instead.
