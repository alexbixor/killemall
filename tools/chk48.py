#!/usr/bin/env python3
"""chk48.py - geometric check of a dumped 48K screen against a float reference raycast.

Measures each 2-px ray column's wall bottom (last row before the floor checker starts, scanning upward) and compares
the implied even wall height with the reference (same camera model as kea48.asm: plane 0.99 (M2.5C), 64 rays, ray centre
r+0.5, height = int(96/perp) made even, clamp 2..96).  usage: chk48.py scr.bin level.bin px py angle256
"""
import pathlib, sys, math, struct

def load_level(path, idx=0):
    b = pathlib.Path(path).read_bytes(); off = 1
    for _ in range(idx + 1):
        n_things = b[off + 7]; size = 8 + 32 * 32 + 3 * n_things
        blob = b[off:off + size]; off += size
    return blob[8:8 + 1024]

def even_height(dist):
    if dist <= 1.0:
        return 96
    h = max(2, min(96, int(96 / dist)))
    return h & ~1 if h > 2 else 2

def ref_heights(cells, px, py, ang256):
    ang = ang256 * 2 * math.pi / 256
    dx, dy = math.cos(ang), math.sin(ang); pxl, pyl = -0.99 * dy, 0.99 * dx
    out = []
    for r in range(64):
        cam = 2 * (r + 0.5) / 64 - 1
        rdx, rdy = dx + pxl * cam, dy + pyl * cam
        mx, my = int(px), int(py)
        ddx = abs(1 / rdx) if rdx else 1e9; ddy = abs(1 / rdy) if rdy else 1e9
        stx, sdx = (-1, (px - mx) * ddx) if rdx < 0 else (1, (mx + 1 - px) * ddx)
        sty, sdy = (-1, (py - my) * ddy) if rdy < 0 else (1, (my + 1 - py) * ddy)
        side = 0
        for _ in range(64):
            if sdx < sdy: sdx += ddx; mx += stx; side = 0
            else: sdy += ddy; my += sty; side = 1
            if cells[my * 32 + mx]: break
        dist = (sdx - ddx) if side == 0 else (sdy - ddy)
        out.append((even_height(dist), dist, cells[my * 32 + mx], side))
    return out

def measured_heights(scr):
    def pix(x, y):
        base = ((y & 0xC0) << 5) + ((y & 7) << 8) + ((y & 0x38) << 2)
        return (scr[base + (x >> 3)] >> (7 - (x & 7))) & 1
    START = [0, 3, 6, 8, 12, 16, 18, 21]      # M2.5C: first pixel of ray r&7 inside its 24-px group (widths 3,3,2,4,4,2,3,3)
    hs = []
    for r in range(64):
        x = 32 + 24 * (r >> 3) + START[r & 7]
        bot = 96
        for wr in range(95, 47, -1):          # scan upward through the floor until the checker breaks
            exp_even = 1 if (wr + x) % 2 == 0 else 0      # checker 0xAA even rows / 0x55 odd rows: lit when x + row is even
            if pix(x, 8 + wr) != exp_even or pix(x + 1, 8 + wr) != 1 - exp_even:
                bot = wr + 1; break
        else:
            bot = 48
        hs.append(2 * (bot - 48))
    return hs

def main():
    scr = pathlib.Path(sys.argv[1]).read_bytes()
    cells = load_level(sys.argv[2])
    px, py, ang = float(sys.argv[3]), float(sys.argv[4]), int(sys.argv[5])
    ref = ref_heights(cells, px, py, ang); meas = measured_heights(scr)
    bad = 0
    for r, ((h, d, code, side), m) in enumerate(zip(ref, meas)):
        if abs(h - m) > 2:
            bad += 1; print("ray %2d ref h %2d (dist %.2f code %d side %d) measured %2d" % (r, h, d, code, side, m))
    print("ref  :", [h for h, _, _, _ in ref])
    print("meas :", meas)
    print("mismatches (>2 rows):", bad, "of 64")

if __name__ == "__main__":
    main()
