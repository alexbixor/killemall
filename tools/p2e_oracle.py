#!/usr/bin/env python3
"""p2e_oracle.py - M2.6 P2E window colour: the EXPECTED 12 x 24 attribute cells, computed independently of the Z80 writer
(src/common/attr.asm + lowcode.asm) from the engine's own zbuf and from each visible sprite drawn ALONE over a zeroed BUF.
Rule (scheme P2E, approved 2 Nov 13:13Z):
  * every cell = T (the level tint, win_tint / at_tint)
  * per byte column: tallest ray hv >= 64 px (wall nearer than 1.5 cells) -> cell rows n .. 11-n = T | BRIGHT with
    n = (48 - min(hv, 96) // 2) // 8 (0..2): the wall lights up, the ceiling / floor cells above and below stay T
  * sprites in vis order (far -> near), only those with an ink (enemies alive, items; corpses / barrels / lamps have none):
    per byte column, the union of the cell rows holding white pixels of those sprites, coloured ink | BRIGHT of the LAST
    (nearest) such sprite in that column (lowcode.asm dc_mark: first = min, last = max, ink = last drawn)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test48 import SYM
from test_game_sprites import call, buf, changed_columns, bytecol_of, BUF0, BUFCOLS, BUFSTR

ATTRWIN = 22564
RAYS_OF = ([0, 1, 2], [3, 4], [5, 6, 7])                      # byte column (bc % 3) -> rays of its 24-px group (ADJTAB)
INK = {1: 3, 7: 3, 2: 4, 3: 4, 4: 4, 5: 4, 6: 4,                # imp magenta, zombie green (THSPR types)
       16: 2, 17: 6, 18: 2, 19: 1, 20: 5}                       # health red, ammo yellow, red key, blue key, shield cyan
CMIN = SYM.get("CMIN", 0x5D20)

def ink_of(typ, state, hp=0):
    """-> attribute byte of the cells holding this sprite's white pixels (0 = it colours nothing): ink | BRIGHT, except
    the blood effects: 0x42 BRIGHT red while a flash is pending, 0x02 red NOT bright for a corpse (M2.6 blood 3 floor stain)."""
    typ &= 31
    if typ < 16 and hp & 0xC0: return 0x42                      # M2.6 blood 1: red flash frames pending (hp bits 6..7)
    if typ < 16 and state == 3: return 0x02                     # M2.6 blood 3: corpse = dark red stain where it fell
    ink = INK.get(typ, 0)
    return ink | 0x40 if ink else 0

def attrs(m): return [[m.memory[ATTRWIN + 32 * r + c] for c in range(24)] for r in range(12)]

def clear_marks(m): m.set_memory_block(CMIN, bytes(48))

def expected(tint, zbuf, sprites, muzzle=False):
    """sprites: far -> near list of (attribute byte from ink_of, [(ray column, row)] white pixels of that sprite drawn alone)."""
    A = [[tint] * 24 for _ in range(12)]
    for bc in range(24):
        hv = max(zbuf[8 * (bc // 3) + r] for r in RAYS_OF[bc % 3])
        if hv >= 64:
            n = 0 if hv >= 96 else (48 - hv // 2) // 8
            for r in range(n, 12 - n): A[r][bc] = tint | 0x40
    marks = {}
    for ink, pix in sprites:
        if not ink: continue
        rows = {}
        for c, r in pix: rows.setdefault(bytecol_of(c), []).append(r)
        for bc, rs in rows.items():
            f, l = min(rs) // 8, max(rs) // 8
            if bc in marks: marks[bc] = [min(marks[bc][0], f), max(marks[bc][1], l), ink]
            else: marks[bc] = [f, l, ink]
    for bc, (f, l, ink) in marks.items():
        for r in range(f, l + 1): A[r][bc] = ink                # ink_of already carries BRIGHT (or not: stain)
    if muzzle: A[9][11] = A[9][12] = 0x46                      # M2.6 muzzle flash: BRIGHT yellow while weapon_frame != 0
    return A

def engine_expectation(m, tint=None, pre=None):
    """After call(m, 'render'): read zbuf + vis, draw every visible coloured thing alone over a zeroed BUF (draw_weapon
    stubbed), restore things / vis / draw_weapon, clear the CMIN marks the extra draws left, return the expected matrix.
    pre = the 128-byte things table as it was BEFORE that render (M2.6 blood 1: the flash counter the render consumed); without
    it the post-render counter is used, which misses the last of the 3 red frames."""
    if tint is None: tint = m.memory[SYM["at_tint"]] if "at_tint" in SYM else 7
    zbuf = bytes(m.memory[SYM["zbuf"]:SYM["zbuf"] + 64])
    things = bytes(m.memory[SYM["things"]:SYM["things"] + 128])
    nvis = m.memory[SYM["nvis"]]; vis = bytes(m.memory[SYM["vis"]:SYM["vis"] + 6 * nvis])
    dw = m.memory[SYM["draw_weapon"]]
    m.set_memory_block(SYM["draw_weapon"], bytes([0xC9]))
    N = BUFCOLS * BUFSTR
    sprites = []
    for i in range(nvis):
        idx = vis[6 * i + 5]
        rec = things[8 * idx:8 * idx + 8]
        ink = ink_of(rec[0], rec[5], (pre or things)[8 * idx + 6])
        if not ink: sprites.append((0, [])); continue
        m.set_memory_block(SYM["things"], bytes(128)); m.set_memory_block(SYM["things"] + 8 * idx, rec)
        m.set_memory_block(BUF0, bytes(N)); call(m, "draw_things")
        cols, pix = changed_columns(bytes(N), buf(m))
        sprites.append((ink, pix))
    m.set_memory_block(SYM["things"], things); m.set_memory_block(SYM["nvis"], bytes([nvis]))
    if nvis: m.set_memory_block(SYM["vis"], vis)
    m.set_memory_block(SYM["draw_weapon"], bytes([dw]))
    clear_marks(m)
    return expected(tint, zbuf, sprites, muzzle=m.memory[SYM["weapon_frame"]] != 0)

def diff(got, exp):
    return [(bc, r, got[r][bc], exp[r][bc]) for r in range(12) for bc in range(24) if got[r][bc] != exp[r][bc]]
