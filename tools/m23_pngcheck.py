#!/usr/bin/env python3
"""m23_pngcheck.py - measure floor lines in a ZEsarUX screenshot PNG (3x nearest, 768x576): per window pixel row (0..95),
count lit pixels in the 3D window (x 64..191) and flag rows that are >= 90% lit across the floor columns while the rows
just above/below are ~50% (checker) -> those are the floor lines. Prints the rows found. usage: m23_pngcheck.py file.png"""
import sys
from PIL import Image
im = Image.open(sys.argv[1]).convert("RGB")
sx = im.size[0] // 256
def lit(x, y):
    r, g, b = im.getpixel((x * sx, y * sx)); return (r + g + b) > 120
rows = []
for wr in range(48, 96):
    y = 8 + wr
    cols = [lit(x, y) for x in range(64, 192)]
    rows.append((wr, sum(cols) / 128.0))
print("floor rows lit fraction (window row: frac):")
print(" ".join("%d:%.2f" % (r, f) for r, f in rows))
lines = [r for r, f in rows if f >= 0.45 and all(abs(f2 - f) > 0.12 for r2, f2 in rows if r2 in (r - 2, r + 2) and f2 < f)]
print("candidate solid rows:", [r for r, f in rows if f > 0.75])