#!/usr/bin/env python3
"""framechk48.py - integrity check of grabbed emulator frames (PNG, 768x576 = 3x of 256x192).
For each frame: count lit pixels inside the window (x 64..191, y 8..103 in Spectrum coords), the floor rows' checker
coverage (rows 48..95 of the window must be at least half 'lit' because the checker/texture is never black there except
where a wall band of a black texel sits), and the wall rows (0..47) which must show some lit texels if any wall is visible.
A half-drawn/cleared frame shows up as a window with (a) a zero/near-zero lit count or (b) floor rows that are all 0.
usage: framechk48.py frames_dir"""
import sys, pathlib
from PIL import Image

def analyse(path):
    img = Image.open(path).convert("RGB"); px = img.load()
    def lit(x, y):           # Spectrum pixel (x, y) -> is it ink (non-black)?
        r, g, b = px[x * 3 + 1, y * 3 + 1]
        return (r + g + b) > 60
    win = sum(1 for y in range(8, 104) for x in range(64, 192) if lit(x, y))
    floor = sum(1 for y in range(56, 104) for x in range(64, 192) if lit(x, y))
    upper = sum(1 for y in range(8, 56) for x in range(64, 192) if lit(x, y))
    # per byte-column: a column whose 96 rows are entirely dark is suspicious (window cleared but not redrawn)
    dark_cols = sum(1 for bx in range(16) if not any(lit(64 + bx * 8 + k, y) for k in range(8) for y in range(8, 104)))
    return win, floor, upper, dark_cols

def main():
    d = pathlib.Path(sys.argv[1]); bad = 0; n = 0
    for f in sorted(d.glob("*.png")):
        win, floor, upper, dark_cols = analyse(f); n += 1
        flag = ""
        if floor < 128 * 48 * 0.40 or dark_cols > 0 or win == 0:
            flag = "  <-- SUSPECT"; bad += 1
        print("%s lit %5d  floor-rows lit %5d/6144  upper lit %5d  all-dark byte columns %d%s" % (f.name, win, floor, upper, dark_cols, flag))
    print("frames %d, suspect (blank/half-drawn) %d" % (n, bad))

if __name__ == "__main__":
    main()
