#!/usr/bin/env python3
"""m25e_hires_proto.py - step E prototype (user 1 Nov 11:3xZ: "make the zombies higher resolution because now they are a mess of blocks").
Takes the 16 x 24 enemy art (assets/sprites/00..07), upscales it 2x with EPX/Scale2x (rounds the staircase diagonals instead of
copying the blocks) to 32 x 48, optionally adds a 50 % dither on the interior (Cauldron II shading), and measures what the engine
would have to store: run lists per source column with a 6-bit v_end (v_end 0..48 does not fit the current (v_end << 3) | code byte).
Output: build/m25e_hires_sheet.png (16x24 vs 32x48 EPX vs 32x48 EPX+dither, 6x zoom) + byte counts per frame on stdout.
usage: .venv/bin/python tools/m25e_hires_proto.py"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from PIL import Image, ImageDraw
ROOT = pathlib.Path(__file__).resolve().parent.parent
NAMES = ["00_imp_walk_a", "01_imp_walk_b", "02_imp_attack", "03_imp_dead", "04_zombie_walk_a", "05_zombie_walk_b", "06_zombie_attack", "07_zombie_dead"]

def load(name):
    rows = [l for l in (ROOT / "assets/sprites" / (name + ".txt")).read_text().splitlines() if l and not l.startswith(";")]
    return [[{"#": 1, "o": 2}.get(ch, 0) for ch in r.ljust(16)[:16]] for r in rows]     # 0 transparent, 1 ink, 2 opaque black

def epx(px):
    """Scale2x/EPX: each pixel P -> 2x2 (E0..E3) from neighbours A(up) B(right) C(left) D(down); ties keep P."""
    h, w = len(px), len(px[0])
    def g(x, y): return px[y][x] if 0 <= x < w and 0 <= y < h else 0
    out = [[0] * (2 * w) for _ in range(2 * h)]
    for y in range(h):
        for x in range(w):
            P = g(x, y); A = g(x, y - 1); B = g(x + 1, y); C = g(x - 1, y); D = g(x, y + 1)
            e0 = C if (C == A and C != D and A != B) else P
            e1 = A if (A == B and A != C and B != D) else P
            e2 = D if (D == C and D != A and C != B) else P
            e3 = B if (B == D and B != A and D != C) else P
            out[2 * y][2 * x], out[2 * y][2 * x + 1], out[2 * y + 1][2 * x], out[2 * y + 1][2 * x + 1] = e0, e1, e2, e3
    return out

def nearest2(px): return [[v for v in r for _ in (0, 1)] for r in px for _ in (0, 1)]

def dither_interior(px):
    """ink pixels whose 4 neighbours are all ink (interior) -> checker: keeps a solid 1-px rim so the figure stays readable."""
    h, w = len(px), len(px[0]); out = [r[:] for r in px]
    def g(x, y): return px[y][x] if 0 <= x < w and 0 <= y < h else 0
    for y in range(h):
        for x in range(w):
            if px[y][x] == 1 and all(g(x + dx, y + dy) == 1 for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))) and (x + y) & 1:
                out[y][x] = 2            # opaque black dot inside the ink = 50 % shade
    return out

def runs(px, box_h, halo=True):
    """column run lists like gen48.runs16 (code 0 transparent, 1 black, 3 white; 1-px halo of black round the ink), art
    bottom-aligned in box_h rows. Returns total bytes (2-byte column offsets + run bytes + terminators)."""
    h, w = len(px), len(px[0]); top = box_h - h
    def ink(x, y): return 0 <= x < w and top <= y < box_h and px[y - top][x] == 1
    total = 2 * w; nruns = 0
    for x in range(w):
        codes = []
        for y in range(box_h):
            v = px[y - top][x] if top <= y < box_h else 0
            if v == 1: codes.append(3)
            elif v == 2: codes.append(1)
            elif halo and any(ink(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy): codes.append(1)
            else: codes.append(0)
        y = 0
        while y < box_h:
            e = y
            while e < box_h and codes[e] == codes[y]: e += 1
            total += 1; nruns += 1; y = e
        total += 1
    return total, nruns

def to_img(px, zoom):
    h, w = len(px), len(px[0]); im = Image.new("RGB", (w, h), (40, 40, 40)); p = im.load()
    for y in range(h):
        for x in range(w):
            p[x, y] = (255, 255, 255) if px[y][x] == 1 else (0, 0, 0) if px[y][x] == 2 else (40, 40, 40)
    return im.resize((w * zoom, h * zoom), Image.NEAREST)

def main():
    rows = []; tot = {"16x24": 0, "32x48 epx": 0, "32x48 epx+dither": 0}
    for name in NAMES:
        src = load(name); e = epx(src); d = dither_interior(e)
        b0, r0 = runs(src, 24); b1, r1 = runs(e, 48); b2, r2 = runs(d, 48)
        tot["16x24"] += b0; tot["32x48 epx"] += b1; tot["32x48 epx+dither"] += b2
        print("%-18s 16x%-2d: %4d B %3d runs | 32x%-2d EPX: %4d B %3d runs | +dither: %4d B %3d runs" % (name, len(src), b0, r0, len(e), b1, r1, b2, r2))
        rows.append((name, to_img(nearest2(src), 6), to_img(e, 6), to_img(d, 6)))
    print("TOTAL 8 enemy frames:", tot, "| zombies only (4..7): %d / %d / %d" % tuple(sum(runs(f(load(n)), bh)[0] for n in NAMES[4:]) for f, bh in ((lambda p: p, 24), (epx, 48), (lambda p: dither_interior(epx(p)), 48))))
    W = 3 * (32 * 6 + 12) + 8; H = sum(48 * 6 + 20 for _ in rows) + 8
    sheet = Image.new("RGB", (W, H), (60, 60, 60)); dr = ImageDraw.Draw(sheet); y = 4
    for name, a, b, c in rows:
        dr.text((4, y), name + "   16x24 (2x nearest) | 32x48 EPX | 32x48 EPX + interior dither", fill=(255, 255, 0)); y += 14
        x = 4
        for im in (a, b, c):
            sheet.paste(im, (x, y + (48 * 6 - im.size[1]))); x += 32 * 6 + 12
        y += 48 * 6 + 6
    out = ROOT / "build/m25e_hires_sheet.png"; sheet.save(out); print("sheet", out, sheet.size)

if __name__ == "__main__":
    main()
