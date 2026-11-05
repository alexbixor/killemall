#!/usr/bin/env python3
"""m25_edit_c_tests.py - M2.5 step C: adapt the Python Z80-core tests / ZEsarUX probes to the 192-px window. Idempotent.
 - harness stubs leave page 0x6A (now FTX): stub 0x5EC0, fx log 0x5EE0, perp_h out 0x5EE8, RET trap 0x5EF0 (DRAM spare
   0x5EC0..0x5EFF, state.asm) ; test_128: TRAP 0x5EC0 / SCR 0x5ED0
 - BUF 0x6100, 24 byte columns x 96 B; ray column of a pixel: PXRAY[(bc % 3) * 8 + bit]; rays of a byte column: RAYS_OF[bc % 3]
 - ATTRWIN 22564, 24 cells per row, frame cols 3 / 28 (x 31 / 224), weapon byte columns 10..13, 3 px per ray column
 - chk48: plane 0.99, ray r measured at its first pixel x = 32 + 24*(r>>3) + START[r&7], checker parity (x + row)"""
import pathlib, re
ROOT = pathlib.Path(__file__).resolve().parent.parent
T = ROOT / "tools"

def edit(name, pairs, marker, regex=()):
    p = T / name; s = p.read_text()
    if marker in s:
        print("%s: already applied" % name); return
    for old, new in pairs:
        assert s.count(old) == 1, "anchor not unique/found in %s: %r" % (name, old[:70])
        s = s.replace(old, new)
    for pat, rep in regex:
        s = re.sub(pat, rep, s)
    p.write_text(s); print("%s: applied" % name)

HARNESS = [(r"0x6A00", "0x5EC0"), (r"0x6AF0", "0x5EF0"), (r"0x6AE0", "0x5EE0"), (r"0x6AE8", "0x5EE8"), (r"0x6A10", "0x5ED0"),
           (r"0xC3, 0xF0, 0x6A", "0xC3, 0xF0, 0x5E"), (r"0x32, 0xE0, 0x6A", "0x32, 0xE0, 0x5E"), (r"0x32, 0xE8, 0x6A", "0x32, 0xE8, 0x5E"),
           (r"0xE0, 0x6A, 0xC9", "0xE0, 0x5E, 0xC9")]

GEO = ('''# M2.5C geometry: 24 byte columns x 96 B at 0x6100; ray columns are 3 px (byte-rounded 3,3,2,4,4,2,3,3 per 24-px group)
BUF0, BUFCOLS, BUFSTR = 0x6100, 24, 96
PXRAY = [0, 0, 0, 1, 1, 1, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 6, 6, 6, 7, 7, 7]      # pixel 0..23 of a group -> ray 0..7
RAYS_OF = ([0, 1, 2], [3, 4], [5, 6, 7])                                                # byte column (bc % 3) -> rays of the group
ADJ = [0, 0, 0, 1, 1, 2, 2, 2]
SLOTM = [0xE0, 0x1C, 0x03, 0xF0, 0x0F, 0xC0, 0x38, 0x07]
def bytecol_of(c): return 3 * (c >> 3) + ADJ[c & 7]
def rays_of(bc): return [8 * (bc // 3) + r for r in RAYS_OF[bc % 3]]
''')

# ---- test48.py (harness + ascii dump of the window)
edit("test48.py", [
 ('    TRAP = 0x6AF0                                               # harness lives in the free page 0x6A (FTX/FTY gap)\n',
  '    TRAP = 0x5EF0                                               # harness lives in the DRAM spare 0x5EC0..0x5EFF (M2.5C: page 0x6A is FTX)\n'),
 ('        for bx in range(8, 24):\n', '        for bx in range(4, 28):\n'),
 ('    attrs = [mem[0x5800 + 32 * r + 8: 0x5800 + 32 * r + 24].hex() for r in range(1, 13)]\n',
  '    attrs = [mem[0x5800 + 32 * r + 4: 0x5800 + 32 * r + 28].hex() for r in range(1, 13)]\n'),
], "DRAM spare 0x5EC0", HARNESS)

# ---- test_game_sprites.py (shared helpers)
edit("test_game_sprites.py", [
 ('TRAP = 0x6AF0\n', 'TRAP = 0x5EF0\n' + GEO),
 ('def buf(m):\n    return bytes(m.memory[0x6000:0x6800])\n',
  'def buf(m):\n    return bytes(m.memory[BUF0:BUF0 + BUFCOLS * BUFSTR])\n'),
 ('    for bc in range(16):\n        for r in range(96):\n            d = a[bc * 128 + r] ^ b[bc * 128 + r]\n'
  '            if d:\n                for bit in range(8):\n                    if d & (0x80 >> bit):\n                        c = bc * 4 + bit // 2\n',
  '    for bc in range(BUFCOLS):\n        for r in range(96):\n            d = a[bc * BUFSTR + r] ^ b[bc * BUFSTR + r]\n'
  '            if d:\n                for bit in range(8):\n                    if d & (0x80 >> bit):\n                        c = 8 * (bc // 3) + PXRAY[(bc % 3) * 8 + bit]\n'),
], "M2.5C geometry", HARNESS)

# ---- test_floor_lines.py
edit("test_floor_lines.py", [
 ('from test_game_sprites import machine, call, set_player, clear_things, buf, SYM\n',
  'from test_game_sprites import machine, call, set_player, clear_things, buf, SYM, BUFCOLS, BUFSTR, rays_of\n'),
 ('    b = buf(m); base = 0x6000 + bytecol * 128 - 0x6000\n', '    b = buf(m); base = bytecol * BUFSTR\n'),
 ('    h = max(m.memory[SYM["zbuf"] + 4 * bytecol + i] for i in range(4))\n',
  '    h = max(m.memory[SYM["zbuf"] + c] for c in rays_of(bytecol))\n'),
 ('    for bc in range(16):\n        ws = floor_words(m, bc)[w0(m, bc):]\n', '    for bc in range(BUFCOLS):\n        ws = floor_words(m, bc)[w0(m, bc):]\n'),
], "rays_of(bytecol)")

# ---- test_ceiling.py
edit("test_ceiling.py", [
 ('from test_game_sprites import machine, call, set_player, clear_things, buf, SYM\n',
  'from test_game_sprites import machine, call, set_player, clear_things, buf, SYM, BUFCOLS, BUFSTR, rays_of, bytecol_of, SLOTM\n'),
 ('    b = buf(m); base = bc * 128\n    return [(b[base + 46 - 2 * w], b[base + 47 - 2 * w]) for w in range(24)]',
  '    b = buf(m); base = bc * BUFSTR\n    return [(b[base + 46 - 2 * w], b[base + 47 - 2 * w]) for w in range(24)]'),
 ('    b = buf(m); base = bc * 128\n    return [w for w in range(24) if (b[base + 48 + 2 * w], b[base + 49 + 2 * w]) == (0xAA, 0xFF)]',
  '    b = buf(m); base = bc * BUFSTR\n    return [w for w in range(24) if (b[base + 48 + 2 * w], b[base + 49 + 2 * w]) == (0xAA, 0xFF)]'),
 ('    h = max(m.memory[SYM["zbuf"] + 4 * bc + i] for i in range(4))\n    return (min(h, 96) + 3) // 4\ndef open_col(m):\n    best = None\n    for bc in range(16):\n',
  '    h = max(m.memory[SYM["zbuf"] + c] for c in rays_of(bc))\n    return (min(h, 96) + 3) // 4\ndef open_col(m):\n    best = None\n    for bc in range(BUFCOLS):\n'),
 ('    bc, mask, top = c // 4, 0xC0 >> (2 * (c & 3)), 48 - h // 2\n    for r in range(top, 48):\n        checked += 1\n        if (b_lo[bc * 128 + r] ^ b_hi[bc * 128 + r]) & mask: leak += 1\n',
  '    bc, mask, top = bytecol_of(c), SLOTM[c & 7], 48 - h // 2\n    for r in range(top, 48):\n        checked += 1\n        if (b_lo[bc * BUFSTR + r] ^ b_hi[bc * BUFSTR + r]) & mask: leak += 1\n'),
], "bytecol_of(c), SLOTM")

# ---- test_sprite_scale.py
edit("test_sprite_scale.py", [
 ('from test_game_sprites import machine, call, set_player, clear_things, set_thing, buf, changed_columns\n',
  'from test_game_sprites import machine, call, set_player, clear_things, set_thing, buf, changed_columns, BUF0, BUFCOLS, BUFSTR\n'),
 ('ATTRWIN = 22568\n', 'ATTRWIN = 22564          # M2.5C: window cols 4..27\n'),
 ('    m.set_memory_block(0x6000, bytes(2048)); call(m, "draw_things"); white = buf(m)\n'
  '    m.set_memory_block(0x6000, bytes([0xFF]) * 2048); call(m, "draw_things"); black = buf(m)\n'
  '    c1, p1 = changed_columns(bytes(2048), white)\n    c2, p2 = changed_columns(bytes([0xFF]) * 2048, black)\n',
  '    N = BUFCOLS * BUFSTR\n'
  '    m.set_memory_block(BUF0, bytes(N)); call(m, "draw_things"); white = buf(m)\n'
  '    m.set_memory_block(BUF0, bytes([0xFF]) * N); call(m, "draw_things"); black = buf(m)\n'
  '    c1, p1 = changed_columns(bytes(N), white)\n    c2, p2 = changed_columns(bytes([0xFF]) * N, black)\n'),
 ('    return [[m.memory[ATTRWIN + 32 * r + c] for c in range(16)] for r in range(12)]\n',
  '    return [[m.memory[ATTRWIN + 32 * r + c] for c in range(24)] for r in range(12)]\n'),
 ('            width = 2 * nc\n', '            width = 3 * nc                                                      # M2.5C: 3 px per ray column\n'),
 ('            bad = [(bc, r) for r in range(12) for bc in range(16) if at[r][bc] != a0[r][bc]]\n',
  '            bad = [(bc, r) for r in range(12) for bc in range(24) if at[r][bc] != a0[r][bc]]\n'),
 (' (c) on-screen width (2 * nc px) == hd * 16/24 within 2 px and centred on column 32 (c0 + nc/2 == 32 +-1)\n',
  ' (c) on-screen width (3 * nc px, M2.5C) == hd * 16/24 within 2 px and centred on column 32 (c0 + nc/2 == 32 +-1)\n'),
], "M2.5C: window cols 4..27", HARNESS)

# ---- test_one_ink.py (needs init_game now: CHJ is RAM built by init_game)
edit("test_one_ink.py", [
 ('from test_game_sprites import machine, call, set_player, clear_things, set_thing, buf, changed_columns\n\nATTRWIN = 22568\n'
  'def attrs(m): return [[m.memory[ATTRWIN + 32 * r + c] for c in range(16)] for r in range(12)]\n',
  'from test_game_sprites import machine, call, set_player, clear_things, set_thing, buf, changed_columns, BUF0, BUFCOLS, BUFSTR\n\n'
  'ATTRWIN = 22564          # M2.5C: window cols 4..27 (24 cells per row)\n'
  'def attrs(m): return [[m.memory[ATTRWIN + 32 * r + c] for c in range(24)] for r in range(12)]\n'),
 ('    call(m, "cls")                       # white ink on black paper everywhere (the game does this before hud_init)\n',
  '    call(m, "init_game", "cls")          # M2.5C: init_game builds CHJ (RAM); cls = white ink on black paper everywhere\n'),
 ('        bad = [(bc, r) for r in range(12) for bc in range(16) if a[r][bc] != 7]\n        nvis = m.memory[SYM["nvis"]]\n',
  '        bad = [(bc, r) for r in range(12) for bc in range(24) if a[r][bc] != 7]\n        nvis = m.memory[SYM["nvis"]]\n'),
 ('        bad = [(bc, r) for r in range(12) for bc in range(16) if a[r][bc] != 7]\n        if bad: print("   FAIL wall code',
  '        bad = [(bc, r) for r in range(12) for bc in range(24) if a[r][bc] != 7]\n        if bad: print("   FAIL wall code'),
 ('        m.set_memory_block(0x6000, bytes(2048)); call(m, "draw_things"); white = buf(m)\n'
  '        m.set_memory_block(0x6000, bytes([0xFF]) * 2048); call(m, "draw_things"); black = buf(m)\n'
  '        cw, pw = changed_columns(bytes(2048), white); cb, pb = changed_columns(bytes([0xFF]) * 2048, black)\n',
  '        N = BUFCOLS * BUFSTR\n'
  '        m.set_memory_block(BUF0, bytes(N)); call(m, "draw_things"); white = buf(m)\n'
  '        m.set_memory_block(BUF0, bytes([0xFF]) * N); call(m, "draw_things"); black = buf(m)\n'
  '        cw, pw = changed_columns(bytes(N), white); cb, pb = changed_columns(bytes([0xFF]) * N, black)\n'),
 ('    for r in range(12): m.set_memory_block(ATTRWIN + 32 * r, bytes([0x55]) * 16)     # the 16 window cells of each row\n',
  '    for r in range(12): m.set_memory_block(ATTRWIN + 32 * r, bytes([0x55]) * 24)     # the 24 window cells of each row\n'),
 ('    poisoned = all(m.memory[ATTRWIN + 32 * r + c] == 0x55 for r in range(12) for c in range(16))\n',
  '    poisoned = all(m.memory[ATTRWIN + 32 * r + c] == 0x55 for r in range(12) for c in range(24))\n'),
 ('    for r in range(12): m.set_memory_block(ATTRWIN + 32 * r, bytes([7]) * 16)\n',
  '    for r in range(12): m.set_memory_block(ATTRWIN + 32 * r, bytes([7]) * 24)\n'),
], "M2.5C: window cols 4..27")

# ---- test_tint.py
edit("test_tint.py", [
 ('ATTRWIN = 22568\ndef win(m): return [m.memory[ATTRWIN + 32 * r + c] for r in range(12) for c in range(16)]\n'
  'def frame(m): return [m.memory[ATTRWIN + 32 * r - 1] for r in range(12)] + [m.memory[ATTRWIN + 32 * r + 16] for r in range(12)]\n',
  'ATTRWIN = 22564          # M2.5C: window cols 4..27, frame cols 3 / 28\n'
  'def win(m): return [m.memory[ATTRWIN + 32 * r + c] for r in range(12) for c in range(24)]\n'
  'def frame(m): return [m.memory[ATTRWIN + 32 * r - 1] for r in range(12)] + [m.memory[ATTRWIN + 32 * r + 24] for r in range(12)]\n'),
], "M2.5C: window cols 4..27")

# ---- test_game_hud.py (frame geometry, weapon bytes, harness)
edit("test_game_hud.py", [
 ('    check(line(m, 7, 7, 18) == bytes([0x01]) + bytes([0xFF]) * 16 + bytes([0x80]), "frame top line y 7 x 63..192")\n'
  '    check(all(pixel(m, 63, y) and pixel(m, 192, y) for y in range(8, 104)), "frame sides x 63 / x 192 rows 8..103")\n',
  '    check(line(m, 7, 3, 26) == bytes([0x01]) + bytes([0xFF]) * 24 + bytes([0x80]), "frame top line y 7 x 31..224 (M2.5C)")\n'
  '    check(all(pixel(m, 31, y) and pixel(m, 224, y) for y in range(8, 104)), "frame sides x 31 / x 224 rows 8..103")\n'),
 ('    check(attr(m, 0, 7, 18) == bytes([2]) * 18, "frame top cells red")\n'
  '    check(all(attr(m, r, 7) == b"\\x02" and attr(m, r, 24) == b"\\x02" for r in range(1, 13)), "frame side cells red")\n',
  '    check(attr(m, 0, 3, 26) == bytes([2]) * 26, "frame top cells red")\n'
  '    check(all(attr(m, r, 3) == b"\\x02" and attr(m, r, 28) == b"\\x02" for r in range(1, 13)), "frame side cells red")\n'),
 ('    call(m, "render"); idle = bytes(m.memory[0x6000 + 6 * 128 + 72: 0x6000 + 6 * 128 + 96]) + bytes(m.memory[0x6000 + 7 * 128 + 72: 0x6000 + 7 * 128 + 96])\n',
  '    W = 0x6100 + 10 * 96                                      # M2.5C: weapon at BUF byte columns 10..13, stride 96\n'
  '    call(m, "render"); idle = bytes(m.memory[W + 72: W + 96]) + bytes(m.memory[W + 96 + 72: W + 96 + 96])\n'),
 ('    fire = bytes(m.memory[0x6000 + 6 * 128 + 72: 0x6000 + 6 * 128 + 96]) + bytes(m.memory[0x6000 + 7 * 128 + 72: 0x6000 + 7 * 128 + 96])\n',
  '    fire = bytes(m.memory[W + 72: W + 96]) + bytes(m.memory[W + 96 + 72: W + 96 + 96])\n'),
], "M2.5C: weapon at BUF", HARNESS)

for name in ("test_game_doors.py", "test_game_enemies.py", "m22_stack.py"):
    edit(name, [], "0x5EC0", HARNESS)

# ---- test_128.py
edit("test_128.py", [('TRAP, SCR = 0x6A00, 0x6A10\n', 'TRAP, SCR = 0x5EC0, 0x5ED0          # M2.5C: DRAM spare (page 0x6A is FTX)\n')], "0x5EC0")

# ---- chk48.py (geometry oracle: plane 0.99, 3-px ray columns, checker parity)
edit("chk48.py", [
 ('the implied even wall height with the reference (same camera model as kea48.asm: plane 0.66, 64 rays, ray centre\n',
  'the implied even wall height with the reference (same camera model as kea48.asm: plane 0.99 (M2.5C), 64 rays, ray centre\n'),
 ('    dx, dy = math.cos(ang), math.sin(ang); pxl, pyl = -0.66 * dy, 0.66 * dx\n',
  '    dx, dy = math.cos(ang), math.sin(ang); pxl, pyl = -0.99 * dy, 0.99 * dx\n'),
 ('    hs = []\n    for r in range(64):\n        x = 64 + 2 * r\n        bot = 96\n        for wr in range(95, 47, -1):          # scan upward through the floor until the checker breaks\n'
  '            exp_even = 1 if wr % 2 == 0 else 0\n',
  '    START = [0, 3, 6, 8, 12, 16, 18, 21]      # M2.5C: first pixel of ray r&7 inside its 24-px group (widths 3,3,2,4,4,2,3,3)\n'
  '    hs = []\n    for r in range(64):\n        x = 32 + 24 * (r >> 3) + START[r & 7]\n        bot = 96\n        for wr in range(95, 47, -1):          # scan upward through the floor until the checker breaks\n'
  '            exp_even = 1 if (wr + x) % 2 == 0 else 0      # checker 0xAA even rows / 0x55 odd rows: lit when x + row is even\n'),
], "M2.5C: first pixel")

# ---- m25b_zes.py (live ZEsarUX probe: screen byte columns 4..27)
edit("m25b_zes.py", [
 ('def scr_col(byte=8):\n', 'def scr_col(byte=4):\n'),
 ('for bc in range(16):\n    h = min(max(zb[4 * bc:4 * bc + 4]), 96); top, bot = 48 - h // 2, 48 + h // 2\n    col = scr_col(8 + bc)\n',
  'RAYS_OF = ([0, 1, 2], [3, 4], [5, 6, 7])                          # M2.5C: rays of byte column bc\n'
  'for bc in range(24):\n    h = min(max(zb[8 * (bc // 3) + r] for r in RAYS_OF[bc % 3]), 96); top, bot = 48 - h // 2, 48 + h // 2\n    col = scr_col(4 + bc)\n'),
 ('print("screen byte col %d (wall rows %d..%d): ceiling dot rows %d/%d, ceiling line rows %s, floor line rows %s" % (8 + bc,',
  'print("screen byte col %d (wall rows %d..%d): ceiling dot rows %d/%d, ceiling line rows %s, floor line rows %s" % (4 + bc,'),
 ('check(dots >= top - 2 * len(lines_c) - 4, "live screen col %d: the open ceiling rows are dots or lines (%d dots + %d lines of %d rows)" % (8 + bc,',
  'check(dots >= top - 2 * len(lines_c) - 4, "live screen col %d: the open ceiling rows are dots or lines (%d dots + %d lines of %d rows)" % (4 + bc,'),
], "M2.5C: rays of byte column")

# ---- run128.py (tearing grabs of the 192x96 window)
edit("run128.py", [
 ('    # --- tearing: 24 random-moment grabs of the 128x96 window\n', '    # --- tearing: 24 random-moment grabs of the 192x96 window (M2.5C: byte columns 4..27)\n'),
 ('            addr = 16384 + ((y & 0xC0) << 5) + ((y & 7) << 8) + ((y & 0x38) << 2) + 8\n            rows.append(rd(addr, 16, 0.02) or b"\\0" * 16)\n'
  '        cols = [sum(1 for r in rows if r[c]) for c in range(16)]\n',
  '            addr = 16384 + ((y & 0xC0) << 5) + ((y & 7) << 8) + ((y & 0x38) << 2) + 4\n            rows.append(rd(addr, 24, 0.02) or b"\\0" * 24)\n'
  '        cols = [sum(1 for r in rows if r[c]) for c in range(24)]\n'),
 ('sum(1 for r in res if r[0] < 0.4 * 1536)))\n', 'sum(1 for r in res if r[0] < 0.4 * 2304)))\n'),
], "M2.5C: byte columns 4..27")

# ---- test48.py NOTHINGS: solid walls (TEXPG -> SOLIDPG) so chk48's checker scan cannot be fooled by a texture row that mimics the
#      checker (M2.5C geo48 view 25.5/3.5/40 ray 56: stone texture rows 86/87 == checker parity at x 200..202 -> measured 76 vs 80
#      while zbuf == float reference; tools/m25c_zbuf_ref.py proves 0/576 rays off by > 2). Geometry = DDA + heights + columns + COPYBUF.
edit("test48.py", [
 ('        m.set_memory_block(SYM["draw_weapon"], bytes([0xC9]))                  # and no weapon graphic over the floor\n',
  '        m.set_memory_block(SYM["draw_weapon"], bytes([0xC9]))                  # and no weapon graphic over the floor\n'
  '        m.set_memory_block(SYM["TEXPG"], bytes([0x5F]) * 16)                   # M2.5C: solid walls (SOLIDPG) -> exact checker scan in chk48\n'),
], "M2.5C: solid walls (SOLIDPG)")
edit("test48.py", [
 ('        m.set_memory_block(SYM["TEXPG"], bytes([0x5F]) * 16)                   # M2.5C: solid walls (SOLIDPG) -> exact checker scan in chk48\n',
  '        m.set_memory_block(SYM["TEXPG"], bytes([0x5F]) * 16)                   # M2.5C: solid walls (SOLIDPG) -> exact checker scan in chk48\n'
  '        m.set_memory_block(SYM["rd_shade"] + 1, bytes([0]))                    # M2.5C: no dark-side 0xAA dither (== checker on even rows)\n'),
], "rd_shade")
