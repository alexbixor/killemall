#!/usr/bin/env python3
"""nx_walk_ref.py - lane D1's compact Python transcription of docs/next_engine_spec_v0.1.md sections 2-4 and 7
(the column walker: PLANE_ADD / DRAW_PIECE / VOID record list + ZBUF per scene) and the section 7 level encoder.
Used by tools/nx_test_walk.py as the oracle while lane R's build/night/ref/<scene>.records.json do not exist.
Tables come from tools/nx_tables.py so they are shared with the Z80 side.

Record format (also what nx_test_walk.py decodes from the Z80 log):
  ["piece", c, ra, count, tex, s, u, v_first, dv]   ["plane", c, h, tex, a, b]   ["void", c, a, b]
"""
import pathlib, sys
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from nx_tables import SIN, COS, RECIP

# ---- section 7: ASCII map -> level0.bin (4 bytes per cell, row-major)
MAP = """BBBBBBBBBBBBBBBBBBBBBBBB########
B......BMMMMMMMMMMMMMMMM#......#
B......WMMMMMMMUUUUUMMMM#......#
B......BMMMMMMtttttttMMM#......#
BBBB.BBBMMMMMsssssssssMM#......#
#..#.MMMMMMMMHHHHHHHHHMM#......#
#..#.......aHHHHHHHHHHHM#......#
#..#.......aHHHHHHHwwHHM#......#
#..#.......aHHHHHHHwwHHM##..####
#..#.MMMMMMMMHHHHHHHHHMM#......#
#..#.MMMMMMMHHHHHHHHHMMM#......#
#..LLLL#################.......#
#.......I.....I................#
#########IIIIIIIIIIIIIIII......#
###########################....#
################################""".split("\n")
# legend: (floor H32, ceil H32, ftex, ctex, wtex, ltex)
OPEN = {'.': (0, 32, 0, 1, 5, 6), 'a': (-8, 64, 3, 2, 5, 6), 'H': (-16, 64, 0, 2, 5, 6), 's': (-8, 64, 3, 2, 5, 6),
        't': (0, 64, 3, 2, 5, 6), 'U': (8, 64, 4, 2, 7, 6), 'w': (-24, 64, 5, 2, 0, 6), 'L': (0, 20, 0, 1, 0, 6)}
SOLID = {'#': 0, 'B': 1, 'M': 2, 'P': 2, 'I': 3, 'W': 4}
SCENES = {"hall": (0x0F80, 0x0780, 512), "corridor": (0x0480, 0x0680, 0), "steps_down": (0x0A60, 0x0733, 40), "altar": (0x0F4D, 0x0766, 768)}

def level_bytes():
    assert len(MAP) == 16 and all(len(r) == 32 for r in MAP), "map must be 16 rows x 32 columns"
    out = bytearray()
    for row in MAP:
        for ch in row:
            if ch in SOLID:
                out += bytes([0, 0, 0x80 | SOLID[ch], 0])            # solid: byte0 = byte1 = 0, byte3 = 0, ltex 0
            else:
                fl, ce, ft, ct, wt, lt = OPEN[ch]
                out += bytes([fl & 255, ce & 255, (lt << 4) | wt, ft | (ct << 4)])
    assert len(out) == 2048
    return bytes(out)

# ---- section 0 helpers
def smul_shr(a, b, s):
    r = (abs(a) * abs(b)) >> s
    return -r if (a < 0) != (b < 0) else r

def ROW(y): return max(0, min(96, (y + 127) >> 8))
def clamp16(v): return max(-32768, min(32767, v))
def R(d): return min(65535, 2 * RECIP[max(8, min(4095, d))])
def s8(b): return b - 256 if b >= 128 else b

def cell_of(level, mx, my):
    if 0 <= mx < 32 and 0 <= my < 16:
        o = (my * 32 + mx) * 4; b0, b1, b2, b3 = level[o:o + 4]
    else:
        b0, b1, b2, b3 = 0, 0, 0x80, 0                                   # outside = solid stone
    return (s8(b0), s8(b1), b2 >> 7, (b2 >> 4) & 7, b2 & 15, b3 & 15, b3 >> 4)   # floor, ceil, solid, ltex, wtex, ftex, ctex

def walk(level, px, py, ang):
    """Sections 2-4 verbatim. Returns (records, zbuf, camera)."""
    a = ang & 1023
    dirx, diry, plx, ply = COS[a], SIN[a], -SIN[a], COS[a]
    mx0, my0 = px >> 8, py >> 8
    eye = cell_of(level, mx0, my0)[0] + 22
    cam = dict(px=px, py=py, a=a, eye=eye, mx=mx0, my=my0, dirx=dirx, diry=diry, plx=plx, ply=ply)
    recs, zbuf = [], [0] * 128

    def y(h, d): return clamp16(48 * 256 - (h - eye) * R(d))

    for c in range(128):
        cam_c = 2 * c + 1 - 128
        rx = dirx + smul_shr(plx, cam_c, 7); ry = diry + smul_shr(ply, cam_c, 7)
        ddx = RECIP[min(4095, abs(rx))]; ddy = RECIP[min(4095, abs(ry))]
        sx = -1 if rx < 0 else 1; sy = -1 if ry < 0 else 1
        fx, fy = px & 255, py & 255
        sdx = min(65535, (fx * ddx) >> 8 if rx < 0 else ((256 - fx) * ddx) >> 8)
        sdy = min(65535, (fy * ddy) >> 8 if ry < 0 else ((256 - fy) * ddy) >> 8)
        mx, my = mx0, my0
        st = dict(ytop=0, ybot=96)
        cur = cell_of(level, mx, my); dprev = 8

        def WALL(h_top, h_bot, tex, d, u, s):
            t_top = h_top
            while t_top > h_bot:
                tile_base = ((t_top - 1) // 32) * 32
                t_bot = max(h_bot, tile_base)
                y_a, y_b = y(t_top, d), y(t_bot, d)
                ra, rb = max(ROW(y_a), st['ytop']), min(ROW(y_b), st['ybot'])
                if ra < rb:
                    v_top = tile_base + 32 - t_top
                    dv = d >> 1
                    v_first = v_top * 256 + smul_shr((ra * 256 + 128) - y_a, dv, 8)
                    count = rb - ra
                    v_last = v_first + (count - 1) * dv
                    if v_last > 8191: v_first -= (v_last - 8191)
                    if v_first < 0: v_first = 0
                    recs.append(["piece", c, ra, count, tex, s, u, v_first, dv])
                t_top = t_bot

        stopped = False
        for _step in range(48):
            if sdx < sdy: d = sdx; sdx = min(65535, sdx + ddx); mx += sx; side = 0
            else:         d = sdy; sdy = min(65535, sdy + ddy); my += sy; side = 1
            d = max(d, 8)
            if d > 4095 or not (0 <= mx < 32 and 0 <= my < 16): break                       # EXHAUST
            fl, ce, _solid, _ltex, _wtex, ftex, ctex = cur
            ya, yb = ROW(y(fl, d)), ROW(y(fl, dprev))                                        # 2. floor
            a_, b_ = max(ya, st['ytop']), min(yb, st['ybot'])
            if a_ < b_: recs.append(["plane", c, fl, ftex, a_, b_])
            st['ybot'] = min(st['ybot'], max(st['ytop'], ya))
            ya, yb = ROW(y(ce, dprev)), ROW(y(ce, d))                                        # 3. ceiling
            a_, b_ = max(ya, st['ytop']), min(yb, st['ybot'])
            if a_ < b_: recs.append(["plane", c, ce, ctex, a_, b_])
            st['ytop'] = max(st['ytop'], min(st['ybot'], yb))
            nxt = cell_of(level, mx, my)                                                     # 4.
            hit = (py + smul_shr(ry, d, 8)) if side == 0 else (px + smul_shr(rx, d, 8))
            u = (hit & 255) >> 3
            s = 0 if d < 384 else 1 if d < 768 else 2 if d < 1536 else 3
            if side == 1: s = min(3, s + 1)
            nfl, nce, nsolid, nltex, nwtex, _f, _c = nxt
            if nsolid:                                                                       # 5.
                WALL(ce, fl, nwtex, d, u, s); zbuf[c] = d; stopped = True; break
            if nfl > fl:                                                                     # 6.
                WALL(nfl, fl, nwtex, d, u, s); st['ybot'] = min(st['ybot'], max(st['ytop'], ROW(y(nfl, d))))
            if nce < ce:                                                                     # 7.
                WALL(ce, nce, nltex, d, u, s); st['ytop'] = max(st['ytop'], min(st['ybot'], ROW(y(nce, d))))
            if st['ytop'] >= st['ybot']: zbuf[c] = d; stopped = True; break                  # 8.
            cur = nxt; dprev = d                                                             # 9.
        if not stopped:                                                                      # EXHAUST
            if st['ytop'] < st['ybot']: recs.append(["void", c, st['ytop'], st['ybot']])
            zbuf[c] = 4095
    return recs, zbuf, cam

def record_bytes(recs):
    """Byte size of the Z80 log for these records (1+10, 1+5, 1+3)."""
    return sum({"piece": 11, "plane": 6, "void": 4}[r[0]] for r in recs)

if __name__ == "__main__":
    lv = level_bytes()
    for name, (px, py, ang) in SCENES.items():
        recs, zbuf, cam = walk(lv, px, py, ang)
        kinds = {k: sum(1 for r in recs if r[0] == k) for k in ("plane", "piece", "void")}
        print("%-10s eye=%3d records=%4d %s log_bytes=%d zbuf[0]=%d zbuf[64]=%d" % (name, cam['eye'], len(recs), kinds, record_bytes(recs), zbuf[0], zbuf[64]))
